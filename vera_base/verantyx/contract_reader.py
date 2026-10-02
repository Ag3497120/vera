"""Conservative raw reader; whole-clause accounting blocks silent requirement loss.

This finite grammar is an explicit coverage limitation. Named intermediate
relations can be explained in any order; procedural order requires markers.
No gold family, caller, plan or per-question mode is accepted by this reader.
"""
from __future__ import annotations
import json
import re
from dataclasses import replace
from .contract_budget import Budget
from .contract_ir import (Boundary, ContractError, Goal, InputBinding, Interface,
    ProgramContract, Region, RequestSource, Requirement, RequirementLedger,
    Span, ValueType, canonical)
from .contract_plan import identifier, infer_goal, boundary_type

ALIASES = {"python":"python_pure_v1","python_pure_v1":"python_pure_v1",
    "javascript":"node_commonjs_sync_v1","js":"node_commonjs_sync_v1","node":"node_commonjs_sync_v1",
    "node_commonjs_sync_v1":"node_commonjs_sync_v1","sqlite":"sqlite_select_v1","sql":"sqlite_select_v1",
    "sqlite_select_v1":"sqlite_select_v1","posix":"posix_numeric_stream_v1","shell":"posix_numeric_stream_v1",
    "posix_numeric_stream_v1":"posix_numeric_stream_v1"}
ID = r"[A-Za-z_][A-Za-z0-9_]{0,31}"
RANGE = r"(-?\d+)\s*(?:\.\.|〜|～|to|から)\s*(-?\d+)"


def is_code_request(raw):
    if not isinstance(raw,str): return False
    visible=re.sub(r"\x60\x60\x60[\s\S]*?\x60\x60\x60|「[^」]*」|\"[^\"]*\"","",raw)
    language=re.search(r"(?<![A-Za-z])(?:Python|JavaScript|SQLite|SQL|POSIX|shell|CommonJS)(?![A-Za-z])|シェル",visible,re.I)
    intent=re.search(r"\b(?:write|create|implement|generate|function|SELECT)\b|作(?:成|って)|書(?:い|く)|実装|生成|関数|コード|返(?:す|して)",visible,re.I)
    action=re.search(r"\b(?:write|create|implement|generate)\b|作(?:成|って)|書(?:い|く)|実装|生成",visible,re.I)
    # The reader-supported query header is itself an explicit code request.
    # Recognise that interface without guessing a family/mode from the task.
    sql_interface=re.search(r"(?:^|[;；。\n])\s*(?:SQLite|sqlite_select_v1)\s+query\s+inputs\s+"+ID+r"(?:\s*,\s*"+ID+r")?\s+columns\s+"+ID+r"(?:\s*,\s*"+ID+r")*\s*(?=[;；。\n]|$)",visible,re.I)
    if sql_interface:
        # An ASCII SQL identifier named what/how/why is not a question cue.
        # Preserve explicit explanatory clauses outside the interface grammar.
        explanatory=re.search(r"(?:^|[;；。\n])\s*(?:explain|what|how|why)\b|とは|何ですか|説明",visible,re.I)
        return bool(action) or not explanatory
    if not action and re.search(r"\b(?:explain|what|how|why)\b|とは|何ですか|説明",visible,re.I): return False
    return bool(language and intent) or bool(re.search(r"(?:コード|関数).*(?:作成|書いて|生成|実装)",visible))


def literal(text):
    text=text.strip()
    if re.fullmatch(r"-?\d+",text): return int(text)
    if text.lower() in ("null","none"): return None
    if text=="[]": return []
    if text=="0.0": return 0.0
    if text.startswith('"') and text.endswith('"'): return json.loads(text)
    if re.fullmatch(ID,text): return {"param":text}
    raise ValueError("literal is not fully interpreted")


def parse_type(text,budget=None):
    def attempt(pattern,value,flags=0):
        if budget: budget.charge("reader",location="parse_type grammar candidate")
        return re.fullmatch(pattern,value,flags)
    text=text.strip()
    m=attempt(r"(?:Nullable\[(.*)\]|(.*)\s+or\s+null)",text,re.I)
    if m: return ValueType("Nullable",item=parse_type(m.group(1) or m.group(2),budget))
    m=attempt(r"(?:Int|integer|整数)\s*\[\s*"+RANGE+r"\s*\]",text,re.I)
    if m: return ValueType("Int",low=int(m.group(1)),high=int(m.group(2)))
    m=attempt(r"ASCII\s+Text\[(\d+)\]",text,re.I)
    if m: return ValueType("Text",max_length=int(m.group(1)))
    m=attempt(r"(?:Record|records?)\s*\{(.*)\}",text,re.I)
    if m:
        fields=[]
        for fragment in re.split(r",\s*(?="+ID+r"\s*:)",m.group(1)):
            name,child=fragment.split(":",1)
            fields.append((name.strip(),parse_type(child,budget)))
        return ValueType("Record",fields=tuple(fields))
    raise ValueError("explicit input type/domain required")


def input_clause(text,budget=None):
    def attempt(pattern,value,flags=0):
        if budget: budget.charge("reader",location="input_clause grammar candidate")
        return re.fullmatch(pattern,value,flags)
    m=attempt(r"(?:table\s+)?("+ID+r")\s*(?::|is|は)\s*Relation\s*\[(.*)\]\s*,?\s*(?:length|max_items)\s*(?:=|:)?\s*(?:0\.\.)?(\d+)(?:\s*,?\s*ordinal\s+("+ID+r"))?",text,re.I)
    if m: return InputBinding(m.group(1),ValueType("Relation",item=parse_type(m.group(2),budget),max_items=int(m.group(3))),ordinal=m.group(4) or "")
    m=attempt(r"(?:input\s+)?("+ID+r")\s*(?::|is|は)\s*(?:Seq|list|array|配列)\s*\[(.*)\]\s*,?\s*(?:length|max(?:_items)?|長さ)\s*(?:=|:|は)?\s*(?:0\s*(?:\.\.|〜|～|to)\s*)?(\d+)",text,re.I)
    if m: return InputBinding(m.group(1),ValueType("Seq",item=parse_type(m.group(2),budget),max_items=int(m.group(3))))
    m=attempt(r"(?:input\s+)?("+ID+r")\s*(?::|is|は)\s*(?:an?\s+)?(?:integer|整数)\s*(?:list|array|配列)(?:\s+with)?\s*,?\s*(?:values?|値|範囲)\s*(?:in|は|:|=)?\s*"+RANGE+r"\s*,?\s*(?:and\s+)?(?:length|長さ|要素数)\s*(?:は|:|=)?\s*(?:0\s*(?:\.\.|〜|～|to)\s*)?(\d+)",text,re.I)
    if m: return InputBinding(m.group(1),ValueType("Seq",item=ValueType("Int",low=int(m.group(2)),high=int(m.group(3))),max_items=int(m.group(4))))
    m=attempt(r"(?:input\s+)?("+ID+r")\s*(?::|is|は)\s*(.*)",text,re.I)
    if m:
        try: return InputBinding(m.group(1),parse_type(m.group(2),budget))
        except ValueError: pass
    return None


def predicate(text,budget=None):
    def attempt(pattern,value,flags=0):
        if budget: budget.charge("reader",location="predicate grammar candidate")
        return re.fullmatch(pattern,value,flags)
    text=text.strip()
    ands=re.split(r"\s+(?:AND|かつ)\s+",text,flags=re.I)
    ors=re.split(r"\s+(?:OR|または)\s+",text,flags=re.I)
    if len(ands)>1 and len(ors)>1:
        raise ContractError("CONTRACT_AMBIGUOUS","reader","mixed AND/OR needs explicit supported grouping")
    parts=ands if len(ands)>1 else ors
    if len(parts)>1:
        joiner=" AND " if len(ands)>1 else " OR "
        return {"op":"and" if len(ands)>1 else "or","args":[predicate(parts[0],budget),predicate(joiner.join(parts[1:]),budget)]}
    if re.match(r"NOT\s+",text,re.I): return {"op":"not","args":[predicate(re.sub(r"^NOT\s+","",text,flags=re.I),budget)]}
    m=attempt(r"("+ID+r"|値)\s*(?:is\s+)?(even|odd|null|not null|偶数|奇数)",text,re.I)
    if m: return {"op":{"even":"even","odd":"odd","null":"is_null","not null":"not_null","偶数":"even","奇数":"odd"}[m.group(2).lower()],"field":"" if m.group(1) in ("value","値") else m.group(1)}
    m=attempt(r"("+ID+r"|値)\s*(==|!=|>=|<=|>|<|=)\s*(.+)",text)
    if m:
        value=literal(m.group(3))
        op={"==":"eq","=":"eq","!=":"ne",">=":"ge","<=":"le",">":"gt","<":"lt"}[m.group(2)]
        field="" if m.group(1) in ("value","値") else m.group(1)
        return {"op":"is_null" if op=="eq" else "not_null","field":field} if value is None and op in ("eq","ne") else {"op":op,"field":field,"value":value}
    m=attempt(r"(-?\d+)\s*(より大きい|以上|より小さい|以下|と等しい|以外)(?:値|もの)",text)
    if m: return {"op":{"より大きい":"gt","以上":"ge","より小さい":"lt","以下":"le","と等しい":"eq","以外":"ne"}[m.group(2)],"field":"","value":int(m.group(1))}
    if text in ("positive","正の値","正数","negative","負の値","負数"):
        return {"op":"gt" if text in ("positive","正の値","正数") else "lt","field":"","value":0}
    if text in ("even","odd","偶数","奇数"):
        return {"op":"even" if text in ("even","偶数") else "odd","field":""}
    raise ValueError("predicate is not fully interpreted")


def operation(text,current,index,budget=None):
    def attempt(pattern,value,flags=0):
        if budget: budget.charge("reader",location="operator grammar candidate")
        return re.fullmatch(pattern,value,flags)
    marker=re.match(r"(?:first|then|next|finally|まず|次に|その後|最後に)\s*[:,、]?\s*",text,re.I)
    explicit=bool(marker)
    if marker: text=text[marker.end():]
    output="v"+str(index)
    out=re.search(r"\s+(?:as|into)\s+("+ID+r")$|\s*->\s*("+ID+r")$",text,re.I)
    if out:
        output=next(x for x in out.groups() if x is not None)
        text=text[:out.start()]; explicit=True
    returns=bool(attempt(r"(?:return\s+.*|.*を返す)",text,re.I))
    text=re.sub(r"^return\s+","",text,flags=re.I)
    text=re.sub(r"を返す$","",text)
    m=attempt(r"(?:keep|filter)\s+(?:("+ID+r")\s+(?:where|by)\s+)?(.+?)(?:\s+only)?",text,re.I)
    if m: return "filter",(m.group(1) or current,),output,{"predicate":predicate(m.group(2),budget)},explicit,returns
    m=attempt(r"(.+?)(?:だけ|のみ)?を残す",text)
    if m: return "filter",(current,),output,{"predicate":predicate(m.group(1),budget)},explicit,returns
    m=attempt(r"(square|abs|upper|lower|strip|length|pluck)(?:\s+("+ID+r"))?(?:\.("+ID+r"))?",text,re.I)
    if m: return "map",(m.group(2) or current,),output,{"subkind":m.group(1).lower(),"field":m.group(3) or ""},explicit,returns
    m=attempt(r"(?:multiply|scale)\s+(?:("+ID+r")\s+)?by\s+(.+)",text,re.I)
    if m: return "map",(m.group(1) or current,),output,{"subkind":"multiply","field":"","value":literal(m.group(2))},explicit,returns
    m=attempt(r"(?:各要素を)?(二乗|平方|絶対値)(?:する|にする|を取る)?",text)
    if m: return "map",(current,),output,{"subkind":"square" if m.group(1) in ("二乗","平方") else "abs","field":""},explicit,returns
    m=attempt(r"sort(?:\s+("+ID+r"))?(?:\s+by\s+("+ID+r"))?\s+(ascending|descending|asc|desc)",text,re.I)
    if m: return "sort",(m.group(1) or current,),output,{"field":m.group(2) or "","descending":m.group(3).lower() in ("descending","desc")},explicit,returns
    if text in ("昇順に並べる","降順に並べる","昇順ソート","降順ソート"):
        return "sort",(current,),output,{"field":"","descending":text.startswith("降")},explicit,returns
    m=attempt(r"(?:dedupe|deduplicate)(?:\s+("+ID+r"))?(?:\s+by\s+("+ID+r"))?(?:\s+keeping first)?",text,re.I)
    if m: return "dedupe",(m.group(1) or current,),output,{"field":m.group(2) or ""},explicit,returns
    if text in ("重複を除く","重複を除去する","先頭を残して重複を除く"):
        return "dedupe",(current,),output,{"field":""},explicit,returns
    m=attempt(r"(?:diff|adjacent differences)(?:\s+(?:of\s+)?("+ID+r"))?",text,re.I)
    if m: return "diff",(m.group(1) or current,),output,{},explicit,returns
    if text in ("隣接差を取る","隣接差分","隣接する要素の差"):
        return "diff",(current,),output,{},explicit,returns
    m=attempt(r"(sum|count|mean|min|max)(?:\s+(?:of\s+)?("+ID+r"))?(?:\.("+ID+r"))?(?:\s+(all ties|all_ties))?",text,re.I)
    if m: return "aggregate",(m.group(2) or current,),output,{"subkind":m.group(1).lower(),"field":m.group(3) or "","all_ties":bool(m.group(4))},explicit,returns
    if text in ("合計","合計する","個数","平均","最小値","最大値"):
        return "aggregate",(current,),output,{"subkind":{"合計":"sum","合計する":"sum","個数":"count","平均":"mean","最小値":"min","最大値":"max"}[text],"field":""},explicit,returns
    m=attempt(r"group\s+("+ID+r")\s+by\s+("+ID+r")(?:\s+aliases\s+("+ID+r")\s*,\s*("+ID+r"))?(?:\s+order\s+(first|key))?",text,re.I)
    if m: return "group",(m.group(1),),output,{"field":m.group(2),"key_alias":m.group(3) or "key","value_alias":m.group(4) or "value","order":m.group(5) or "first"},True,returns
    m=attempt(r"join\s+("+ID+r")\s+on\s+("+ID+r")\s+with\s+("+ID+r")\s+on\s+("+ID+r")\s+project\s+(.+)",text,re.I)
    if m:
        projection=[]
        for part in m.group(5).split(","):
            col=attempt(r"\s*(left|right)\.("+ID+r")\s+as\s+("+ID+r")\s*",part,re.I)
            if not col: return None
            projection.append({"side":col.group(1).lower(),"field":col.group(2),"alias":col.group(3)})
        return "join",(m.group(1),m.group(3)),output,{"left_key":m.group(2),"right_key":m.group(4),"projection":projection},explicit,returns
    m=attempt(r"not_exists\s+("+ID+r")\s+on\s+("+ID+r")\s+in\s+("+ID+r")\s+on\s+("+ID+r")",text,re.I)
    if m: return "not_exists",(m.group(1),m.group(3)),output,{"left_key":m.group(2),"right_key":m.group(4)},explicit,returns
    m=attempt(r"ratio\s+("+ID+r")\s+numerator\s+("+ID+r")\s+denominator\s+("+ID+r")",text,re.I)
    if m: return "ratio",(m.group(1),),output,{"numerator":m.group(2),"denominator":m.group(3),"zero":None},explicit,returns
    return None


def read_requirements(raw,budget=None,*,profile=None):
    budget=budget or Budget()
    if not isinstance(raw,str): raise ContractError("REQUEST_TYPE_UNSUPPORTED","reader","raw request must be text")
    if len(raw)>4096: raise ContractError("REQUEST_SIZE_UNSUPPORTED","reader","request exceeds 4096 code points")
    try: raw.encode("utf-8")
    except UnicodeEncodeError: raise ContractError("REQUEST_ENCODING_UNSUPPORTED","reader","unpaired Unicode surrogate is not a valid UTF-8 request")
    regions=tuple(Region(Span(m.start(),m.end(),m.group()),"code" if m.group().startswith("\x60") else "quotation") for m in re.finditer(r"\x60\x60\x60[\s\S]*?\x60\x60\x60|「[^」]*」",raw))
    source=RequestSource(raw,regions)
    requirements=[]; unknown=[]; goals=[]; inputs=[]; boundaries=[]
    function=""; parameters=(); kw=(); columns=(); argv=(); current=""; returned=""; return_kind=""; steps=[]; selected=profile
    def req(kind,span,target="",payload=None):
        budget.charge("requirements",location=kind)
        r=Requirement("r"+str(len(requirements)),kind,(span,),target,payload_json=canonical(payload or {}))
        requirements.append(r); return r.id
    # Periods in integer ranges and field references stay inside clauses.
    pieces=list(re.finditer(r"[^;；。\n]+",raw))
    for piece in pieces:
        a,b=piece.start(),piece.end()
        while a<b and raw[a].isspace(): a+=1
        while b>a and raw[b-1].isspace(): b-=1
        if a==b: continue
        span=Span(a,b,raw[a:b]); text=span.text.strip()
        budget.charge("reader",location="clause classification")
        protected=[r for r in regions if r.span.start<b and a<r.span.end]
        if protected:
            if re.fullmatch(r"(?:example|quoted material|引用|例)\s*:?\s*(?:\x60\x60\x60[\s\S]*\x60\x60\x60|「[^」]*」)",text,re.I):
                req("quoted_material",span,payload={"role":"data"}); continue
            unknown.append(span); continue
        budget.charge("reader",location="rule:language")
        label=re.fullmatch(r"(?:(?:use|language:|言語は|言語:)\s*)?(\w+)",text,re.I)
        if label and label.group(1).lower() in ALIASES:
            found=ALIASES[label.group(1).lower()]
            if selected and selected!=found: raise ContractError("CONTRACT_CONFLICT","reader","conflicting backend profiles")
            selected=found; req("profile",span,payload={"profile":found}); continue
        budget.charge("reader",location="rule:function interface")
        header=re.fullmatch(r"(?:(Python|JavaScript|JS|Node|python_pure_v1|node_commonjs_sync_v1)(?:\s+|で))?(?:(?:write|create|implement)\s+)?(?:function|関数)\s+("+ID+r")\s*\(([^()]*)\)(?:\s*(?:を作成(?:して)?|を実装(?:して)?|を書いて))?",text,re.I)
        if header:
            if function: raise ContractError("CONTRACT_CONFLICT","reader","multiple function interfaces")
            if header.group(1):
                found=ALIASES[header.group(1).lower()]
                if selected and selected!=found: raise ContractError("CONTRACT_CONFLICT","reader","conflicting backend profiles")
                selected=found
            function=header.group(2); args=[p.strip() for p in header.group(3).split(",") if p.strip()]
            if any(p!="*" and not identifier(p,selected or "") for p in args) or args.count("*")>1:
                raise ContractError("INTERFACE_UNSUPPORTED","reader","defaults/rest/invalid parameters outside profile")
            if "*" in args:
                star=args.index("*"); kw=tuple(args[star+1:]); args.remove("*")
            parameters=tuple(args); current=parameters[0] if parameters else ""
            req("interface",span,payload={"name":function,"parameters":parameters,"keyword_only":kw}); continue
        budget.charge("reader",location="rule:SQL interface")
        sql_header=re.fullmatch(r"(?:SQLite|sqlite_select_v1)\s+query\s+inputs\s+("+ID+r"(?:\s*,\s*"+ID+r")?)\s+columns\s+("+ID+r"(?:\s*,\s*"+ID+r")*)",text,re.I)
        if sql_header:
            if selected and selected!="sqlite_select_v1": raise ContractError("CONTRACT_CONFLICT","reader","conflicting SQL profile")
            selected="sqlite_select_v1"; function="query"; parameters=tuple(n.strip() for n in sql_header.group(1).split(",")); columns=tuple(n.strip() for n in sql_header.group(2).split(",")); current=parameters[0]
            req("interface",span,payload={"name":function,"parameters":parameters,"keyword_only":[],"columns":columns}); continue
        budget.charge("reader",location="rule:stdin interface")
        if re.fullmatch(r"(?:POSIX\s+)?(?:numeric stdin stream|整数stdinストリーム|改行区切り整数stdin)",text,re.I):
            if selected and selected!="posix_numeric_stream_v1": raise ContractError("CONTRACT_CONFLICT","reader","conflicting interface")
            selected="posix_numeric_stream_v1"; function="stream"; parameters=("stdin",); current="stdin"
            req("interface",span,payload={"name":function,"parameters":parameters,"keyword_only":[]}); continue
        budget.charge("reader",location="rule:argv interface")
        shell_header=re.fullmatch(r"POSIX\s+numeric stdin stream\s+argv\s+("+ID+r"(?:\s*,\s*"+ID+r")?)",text,re.I)
        if shell_header:
            if selected and selected!="posix_numeric_stream_v1": raise ContractError("CONTRACT_CONFLICT","reader","conflicting shell profile")
            selected="posix_numeric_stream_v1"; function="stream"; argv=tuple(n.strip() for n in shell_header.group(1).split(",")); parameters=("stdin",)+argv; current="stdin"
            req("interface",span,payload={"name":function,"parameters":parameters,"keyword_only":[],"argv":argv}); continue
        budget.charge("reader",location="rule:input domain")
        try: binding=input_clause(text,budget)
        except (ValueError,TypeError): binding=None
        if binding:
            if any(x.name==binding.name for x in inputs): raise ContractError("CONTRACT_CONFLICT","reader","duplicate input domain")
            inputs.append(binding); req("domain",span,binding.name,{"type":json.loads(canonical(binding.type)),"ordinal":binding.ordinal}); continue
        budget.charge("reader",location="rule:effect")
        if re.fullmatch(r"(?:do not mutate (?:the )?inputs?|inputs? (?:must be )?unchanged|入力を変更しない|入力不変)",text,re.I):
            req("effect",span,payload={"effect":"pure_input_unchanged"}); continue
        budget.charge("reader",location="rule:input empty")
        empty=re.fullmatch(r"(?:if\s+("+ID+r")\s+is empty,?\s+return|("+ID+r")が空なら)\s*(null|None|\[\]|-?\d+|0\.0)(?:を返す)?",text,re.I)
        if empty:
            symbol=empty.group(1) or empty.group(2); value=literal(empty.group(3)); rid=req("input_empty",span,symbol,{"value":value})
            boundaries.append(Boundary("input_empty",symbol,canonical(value),rid)); continue
        budget.charge("reader",location="rule:aggregate empty")
        em=re.fullmatch(r"empty\s+(sum|count|mean|min|max)(?:\s+of\s+("+ID+r"))?\s*(?:is|=)\s*(null|None|-?\d+|0\.0)",text,re.I)
        if em:
            matching=[g for g in goals if g.kind=="aggregate" and g.config.get("subkind")==em.group(1).lower() and (not em.group(2) or g.inputs==(em.group(2),))]
            if len(matching)!=1: unknown.append(span); continue
            old=matching[0]; value=literal(em.group(3)); cfg=old.config
            if "empty" in cfg and cfg["empty"]!=value: raise ContractError("CONTRACT_CONFLICT","reader","conflicting aggregate empty policies")
            cfg["empty"]=value; rid=req("aggregate_empty",span,old.output,{"value":value,"goal_id":old.id})
            goals[goals.index(old)]=replace(old,config_json=canonical(cfg),requirement_ids=old.requirement_ids+(rid,)); continue
        budget.charge("reader",location="rule:return")
        ret=re.fullmatch(r"(?:return|返却)\s+(?:(Int|integer|list|array|Float64)\s+)?("+ID+r")|("+ID+r")を返す",text,re.I)
        # Reserved operation names are parsed as computations before bare symbols.
        if ret and (ret.group(2) or ret.group(3)) not in ("sum","count","mean","min","max","square","abs","diff"):
            symbol=ret.group(2) or ret.group(3)
            if returned and returned!=symbol: raise ContractError("CONTRACT_CONFLICT","reader","conflicting return values")
            returned=symbol; return_kind=ret.group(1) or ""; req("return",span,symbol,{"symbol":symbol,"kind":return_kind}); continue
        budget.charge("reader",location="rule:operation")
        try: op=operation(text,current,len(goals),budget)
        except (ValueError,TypeError): op=None
        if op:
            kind,parents,out,cfg,explicit,returns=op
            if selected=="sqlite_select_v1" and (kind in ("aggregate","ratio") or kind=="map" and cfg.get("subkind")=="pluck"):
                if len(columns)!=1: raise ContractError("BACKEND_UNSUPPORTED","reader","scalar SQL projection needs one declared output column")
                cfg["alias"]=columns[0]
            rid=req("relation",span,out,{"kind":kind,"inputs":parents,"output":out,"config":cfg})
            goals.append(Goal("g"+str(len(goals)),kind,parents,out,canonical(cfg),(rid,)))
            steps.append(explicit); current=out
            if returns: returned=out; req("return",span,out,{"symbol":out,"kind":""})
            continue
        unknown.append(span)
    ledger=RequirementLedger(source.hash,tuple(requirements),tuple(unknown))
    if unknown:
        raise ContractError("REQUIREMENT_UNREAD","reader","uninterpreted mandatory clauses",{"source":json.loads(canonical(source)),"ledger":json.loads(canonical(ledger))})
    if not selected or not function or not parameters or not goals or not returned:
        raise ContractError("CONTRACT_INCOMPLETE","reader","profile, interface, input domains, computation, return must be explicit",{"ledger":json.loads(canonical(ledger))})
    if len(goals)>1 and not all(steps):
        raise ContractError("CONTRACT_AMBIGUOUS","reader","multiple operations need explicit order or named intermediate results",{"ledger":json.loads(canonical(ledger))})
    if set(x.name for x in inputs)!=set(parameters):
        raise ContractError("CONTRACT_INCOMPLETE","reader","every parameter needs an explicit input domain")
    if len(boundaries)>1: raise ContractError("BACKEND_UNSUPPORTED","reader","one named input-empty override is supported")
    ordered=tuple(replace(next(x for x in inputs if x.name==n),kind="keyword_only" if n in kw else "positional_or_keyword") for n in parameters)
    if any(b.symbol not in parameters or next(x for x in ordered if x.name==b.symbol).type.kind not in ("Seq","Relation") for b in boundaries):
        raise ContractError("TYPE_OR_BINDING_FAILURE","reader","input-empty trigger must name a collection input")
    # Ledger is immutable before any type-binding operation.
    budget.charge("readings"); budget.capacity("scopes",1)
    symbols={x.name:x.type for x in ordered}; pending=list(goals)
    while pending:
        progress=False
        for goal in list(pending):
            budget.charge("reader",location="contract symbol binding")
            if not all(n in symbols for n in goal.inputs): continue
            symbols[goal.output]=infer_goal(goal,tuple(symbols[n] for n in goal.inputs),symbols,selected,budget)
            pending.remove(goal); progress=True
        if not progress: raise ContractError("TYPE_OR_BINDING_FAILURE","reader","unbound intermediate/dependency cycle")
    if returned not in symbols: raise ContractError("TYPE_OR_BINDING_FAILURE","reader","unbound return symbol")
    rt=boundary_type(symbols[returned],tuple(boundaries))
    if return_kind and rt.kind!={"int":"Int","integer":"Int","float64":"Float64","list":"Seq","array":"Seq"}[return_kind.lower()]:
        raise ContractError("CONTRACT_CONFLICT","reader","stated return shape differs from computation")
    if any(b.value is None and rt.kind!="Nullable" for b in boundaries):
        raise ContractError("BACKEND_UNSUPPORTED","reader","input-empty output union is not yet represented by this reader")
    contract=ProgramContract(source.hash,ledger.hash,selected,Interface(function,parameters,kw,columns,True,argv),ordered,tuple(goals),returned,rt,tuple(r.id for r in requirements),tuple(boundaries))
    return source,ledger,contract
