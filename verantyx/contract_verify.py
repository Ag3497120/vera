"""Source/contract/plan gates and finite execution checks, separate from emitters.

Expected values below interpret frozen desired relations, never emitted code
or legacy code_compose.reference. They do not certify a raw reading: that
requires an independent R/E oracle. Finite witnesses are not universal proof.
"""
from __future__ import annotations
import copy
import json
import math
import time
from dataclasses import asdict, replace
from .contract_ir import ContractError, Goal, ValueType, canonical, digest
from .contract_plan import infer_goal, shape_equal, refines, boundary_type, PARTS
from .contract_budget import Budget
from .contract_sandbox import run_artifact


class _VerifierAccount:
    def __init__(self,budget): self.budget=budget
    def charge(self,key,cost=1,location=""):
        self.budget.charge("verifier",cost,location)
    def capacity(self,key,size,location=""):
        self.budget.charge("verifier",1,location)


def accepts(value,typ,*,domain=False):
    if typ.kind=="Nullable": return value is None or accepts(value,typ.item,domain=domain)
    if typ.kind=="Int":
        return type(value) is int and (not domain or (typ.low is None or value>=typ.low) and (typ.high is None or value<=typ.high))
    if typ.kind=="Float64": return type(value) is float and math.isfinite(value)
    if typ.kind=="Text":
        return type(value) is str and value.isascii() and all(32<=ord(c)<=126 for c in value) and (not domain or typ.max_length is None or len(value)<=typ.max_length)
    if typ.kind in ("Seq","Relation"):
        return type(value) is list and (not domain or typ.max_items is None or len(value)<=typ.max_items) and all(accepts(x,typ.item,domain=domain) for x in value)
    if typ.kind=="Record":
        return type(value) is dict and set(value)=={name for name,t in typ.fields} and all(accepts(value[name],t,domain=domain) for name,t in typ.fields)
    return False


def same_value(a,b,*,js=False):
    if type(a) is not type(b):
        if not(js and type(a) in (int,float) and type(b) in (int,float)): return False
    if isinstance(a,list):
        return len(a)==len(b) and all(same_value(x,y,js=js) for x,y in zip(a,b))
    if isinstance(a,dict):
        return set(a)==set(b) and all(same_value(a[k],b[k],js=js) for k in a)
    return a==b


def _get(row,field):
    return row[field] if field else row


def _operand(value,bindings):
    return bindings[value["param"]] if isinstance(value,dict) else value


def _truth(p,row,bindings,budget):
    budget.charge("verifier",location="predicate semantic witness")
    op=p["op"]
    if op in ("not","and","or"):
        values=[_truth(child,row,bindings,budget) for child in p["args"]]
        if op=="not": return None if values[0] is None else not values[0]
        if op=="and": return False if False in values else True if all(v is True for v in values) else None
        return True if True in values else False if all(v is False for v in values) else None
    a=_get(row,p.get("field",""))
    if op=="is_null": return a is None
    if op=="not_null": return a is not None
    b=_operand(p.get("value"),bindings)
    if a is None or b is None and op not in ("even","odd"): return None
    if op=="even": return a%2==0
    if op=="odd": return a%2!=0
    if op=="eq": return a==b
    if op=="ne": return a!=b
    if op=="lt": return a<b
    if op=="le": return a<=b
    if op=="gt": return a>b
    return a>=b


def _aggregate(rows,cfg,budget):
    kind=cfg["subkind"]
    if not rows: return [] if cfg.get("all_ties") else cfg.get("empty",0 if kind in ("sum","count") else None)
    if kind=="count": return len(rows)
    values=[]
    for row in rows:
        budget.charge("verifier",location="aggregate semantic witness")
        values.append(_get(row,cfg.get("field","")))
    if kind=="sum": return sum(values)
    if kind=="mean": return float(sum(values)/len(values))
    extreme=min(values) if kind=="min" else max(values)
    return [copy.deepcopy(row) for row in rows if _get(row,cfg.get("field",""))==extreme] if cfg.get("all_ties") else extreme


def interpret(contract,bindings,budget):
    """Evaluate required relations, independent of supplied plan and lowering."""
    env=copy.deepcopy(bindings)
    for b in contract.boundaries:
        budget.charge("verifier",location="entry-empty witness")
        if b.trigger=="input_empty" and len(env[b.symbol])==0: return copy.deepcopy(b.value)
    pending=list(contract.goals)
    grouped=set()
    while pending:
        progress=False
        for g in list(pending):
            budget.charge("verifier",location="semantic dependency")
            if any(n not in env for n in g.inputs): continue
            rows=env[g.inputs[0]]; cfg=g.config; field=cfg.get("field",""); kind=g.kind
            if kind=="filter": result=[copy.deepcopy(r) for r in rows if _truth(cfg["predicate"],r,env,budget) is True]
            elif kind=="map":
                result=[]
                for row in rows:
                    budget.charge("verifier",location="map semantic witness")
                    value=_get(row,field); sub=cfg["subkind"]
                    if sub=="square": value=value*value
                    elif sub=="abs": value=abs(value)
                    elif sub=="multiply": value=value*_operand(cfg["value"],env)
                    elif sub=="upper": value=value.upper()
                    elif sub=="lower": value=value.lower()
                    elif sub=="strip": value=value.strip(" ")
                    elif sub=="length": value=len(value)
                    if field and sub!="pluck":
                        mapped=copy.deepcopy(row); mapped[field]=value; value=mapped
                    result.append(value)
            elif kind=="sort": result=sorted(copy.deepcopy(rows),key=lambda r:_get(r,field),reverse=cfg.get("descending",False))
            elif kind=="dedupe":
                seen=[]; result=[]
                for row in rows:
                    budget.charge("verifier",location="dedupe semantic witness")
                    key=_get(row,field)
                    # Equality only for the explicitly bound scalar key.
                    found=False
                    for old in seen:
                        budget.charge("verifier",location="dedupe key comparison")
                        if type(key) is type(old) and key==old: found=True; break
                    if not found: seen.append(key); result.append(copy.deepcopy(row))
            elif kind=="diff":
                result=[]
                for i in range(1,len(rows)):
                    budget.charge("verifier",location="adjacent difference witness"); result.append(rows[i]-rows[i-1])
            elif kind=="group":
                groups={}
                for row in rows:
                    budget.charge("verifier",location="group semantic witness")
                    groups.setdefault(row[field],[]).append(copy.deepcopy(row))
                result=list(groups.items())
                if cfg.get("order","first")=="key": result.sort(key=lambda pair:pair[0])
                grouped.add(g.output)
            elif kind=="aggregate":
                if g.inputs[0] in grouped:
                    original=next(old for old in contract.goals if old.output==g.inputs[0])
                    result=[{original.config.get("key_alias","key"):key,original.config.get("value_alias","value"):_aggregate(group,cfg,budget)} for key,group in rows]
                else:
                    result=_aggregate(rows,cfg,budget)
                    if contract.profile=="sqlite_select_v1" and not cfg.get("all_ties"): result=[{cfg["alias"]:result}]
            elif kind in ("join","not_exists"):
                other=env[g.inputs[1]]; result=[]
                for left in rows:
                    matches=[]
                    for right in other:
                        budget.charge("verifier",location="join key comparison")
                        if left[cfg["left_key"]]==right[cfg["right_key"]]: matches.append(right)
                    if kind=="not_exists":
                        if not matches: result.append(copy.deepcopy(left))
                    else:
                        for right in matches:
                            result.append({col["alias"]:(left if col["side"]=="left" else right)[col["field"]] for col in cfg["projection"]})
            elif kind=="ratio":
                result=[]
                for row in rows:
                    budget.charge("verifier",location="ratio semantic witness")
                    a,b=row[cfg["numerator"]],row[cfg["denominator"]]
                    result.append(None if b==0 else 0.0 if a==0 else a/b)
            else: raise ContractError("VERIFICATION_FAILED","verifier","unknown desired relation")
            if contract.profile=="sqlite_select_v1" and kind in ("ratio","map") and (kind=="ratio" or cfg.get("subkind")=="pluck"):
                result=[{cfg["alias"]:v} for v in result]
            env[g.output]=result; pending.remove(g); progress=True
        if not progress: raise ContractError("VERIFICATION_FAILED","verifier","required relations are cyclic")
    return env[contract.return_symbol]


def _sample(typ,index,field_index=0):
    if typ.kind=="Nullable": return None if (index+field_index)%7==6 else _sample(typ.item,index,field_index)
    if typ.kind=="Int":
        candidates=[typ.low,typ.high,0,-1,1,2,-2,3]
        value=candidates[(index+field_index*3)%len(candidates)]
        return max(typ.low,min(typ.high,value))
    if typ.kind=="Text": return ("a","b","A"," a ","","z")[((index+field_index)%6)][:typ.max_length]
    if typ.kind=="Record": return {name:_sample(t,index,field_index*11+j+1) for j,(name,t) in enumerate(typ.fields)}
    raise ContractError("VERIFICATION_BUDGET","verifier","no registered witness selection for input")


def _nonnull(typ,index=0,input_index=0):
    if typ.kind=="Nullable": return _nonnull(typ.item,index,input_index)
    if typ.kind=="Record": return {name:_nonnull(t,index,input_index*11+j+1) for j,(name,t) in enumerate(typ.fields)}
    return _sample(typ,index,input_index)


def _atoms(predicate,budget):
    budget.charge("verifier",location="required predicate controls")
    if predicate["op"] in ("and","or","not"):
        for child in predicate["args"]: yield from _atoms(child,budget)
    else: yield predicate


def _values(typ,threshold=None):
    nullable=typ.kind=="Nullable"; base=typ.item if nullable else typ
    if base.kind=="Int": candidates=[base.low,base.high,0,-1,1,2]
    elif base.kind=="Text": candidates=["","a","b","A"," a ","z"]
    else: candidates=[_nonnull(base)]
    if type(threshold) is int: candidates[0:0]=[threshold-1,threshold,threshold+1]
    elif type(threshold) is str: candidates[0:0]=[threshold]
    if nullable: candidates.append(None)
    result=[]
    for value in candidates:
        if accepts(value,typ,domain=True) and not any(same_value(value,old) for old in result): result.append(value)
    return result


def _ordinalize(binding,rows):
    if binding.ordinal:
        typ=binding.type.item.field(binding.ordinal)
        for j,row in enumerate(rows): row[binding.ordinal]=typ.low+j
    if not accepts(rows,binding.type,domain=True):
        raise ContractError("VERIFICATION_BUDGET","verifier","required control exceeds input/ordinal domain",binding.name)


def _required_controls(contract,bindings_list,budget,validate_only=False):
    """Pack requirement-derived controls without replacing baseline witnesses.

    Coverage is checked against actual bindings. Seeds alone are never evidence.
    Controls concern the declared domain and frozen requirements, not a candidate
    artifact or evaluator family/mode. Lack of room or control search is held.
    """
    by_name={b.name:b for b in contract.inputs}; coverage=[]
    def row_control(binding,label,row,predicate):
        budget.charge("verifier",location=label)
        if binding.type.max_items==0:
            coverage.append({"control":label,"domain_inapplicable":"max_items=0"}); return
        found=next((i for i,bindings in enumerate(bindings_list) if any(predicate(r) for r in bindings[binding.name])),None)
        if found is None and validate_only:
            raise ContractError("VERIFICATION_BUDGET","verifier","final packing erased a required row control",label)
        if found is None:
            for i in (2,3,4,6,7,8,11,1):
                rows=bindings_list[i][binding.name]
                if len(rows)>=binding.type.max_items: continue
                candidate=copy.deepcopy(rows)+[copy.deepcopy(row)]
                _ordinalize(binding,candidate)
                if not predicate(candidate[-1]): continue
                bindings_list[i][binding.name]=candidate; found=i; break
        if found is None:
            raise ContractError("VERIFICATION_BUDGET","verifier","required differential control does not fit 12 witnesses/input length",label)
        coverage.append({"control":label,"case":found})
    for binding in contract.inputs:
        if binding.type.kind not in ("Seq","Relation"): continue
        item=binding.type.item
        if item.kind!="Record": continue
        nullable=[name for name,t in item.fields if t.kind=="Nullable"]
        base=_nonnull(item,3,contract.inputs.index(binding))
        if nullable:
            row_control(binding,binding.name+":nullable:nonnull",base,
                lambda row,names=tuple(nullable):all(row[n] is not None for n in names))
            all_null=copy.deepcopy(base)
            for name in nullable: all_null[name]=None
            row_control(binding,binding.name+":nullable:all_null",all_null,
                lambda row,names=tuple(nullable):all(row[n] is None for n in names))
        for name in nullable:
            row=copy.deepcopy(base);row[name]=None
            row_control(binding,binding.name+":nullable:only:"+name,row,
                lambda row,name=name,names=tuple(nullable):row[name] is None and all(row[n] is not None for n in names if n!=name))
        for goal in contract.goals:
            if goal.kind!="filter" or goal.inputs!=(binding.name,): continue
            predicate=goal.config["predicate"]
            for atom in _atoms(predicate,budget):
                field=atom.get("field","")
                if not field: continue
                if field==binding.ordinal:
                    raise ContractError("VERIFICATION_UNSUPPORTED","verifier","differential ordinal-predicate coverage is not registered")
                target=item.field(field); target_base=target.item if target.kind=="Nullable" else target
                for peer,peer_type in item.fields:
                    peer_base=peer_type.item if peer_type.kind=="Nullable" else peer_type
                    if peer in (field,binding.ordinal) or peer_base.kind!=target_base.kind: continue
                    changed=copy.deepcopy(predicate)
                    def rename(p):
                        if p["op"] in ("and","or","not"):
                            for child in p["args"]: rename(child)
                        elif p.get("field","")==field: p["field"]=peer
                    rename(changed)
                    def distinguishes(row,p=predicate,q=changed,bindings=bindings_list[3]):
                        return (_truth(p,row,bindings,budget) is True)!=(_truth(q,row,bindings,budget) is True)
                    threshold=_operand(atom.get("value"),bindings_list[3])
                    row=None
                    for seed in range(8):
                        seed_row=_nonnull(item,seed,contract.inputs.index(binding))
                        for a in _values(target,threshold):
                            for b in _values(peer_type,threshold):
                                trial=copy.deepcopy(seed_row);trial[field]=a;trial[peer]=b
                                if distinguishes(trial): row=trial;break
                            if row is not None: break
                        if row is not None: break
                    if row is None:
                        # A finite unsuccessful search is not a proof of
                        # equivalence or of an empty distinguishing domain.
                        raise ContractError("VERIFICATION_UNSUPPORTED","verifier","predicate/peer differential control not found in registered search",{"goal":goal.id,"field":field,"peer":peer})
                    row_control(binding,goal.id+":predicate_field:"+field+":"+peer,row,distinguishes)
    for goal in contract.goals:
        if goal.kind not in ("join","not_exists"): continue
        if any(name not in by_name for name in goal.inputs):
            raise ContractError("VERIFICATION_UNSUPPORTED","verifier","independent join controls for intermediate inputs are not registered")
        left,right=(by_name[n] for n in goal.inputs);cfg=goal.config
        lk,rk=cfg["left_key"],cfg["right_key"]
        if lk==left.ordinal or rk==right.ordinal:
            raise ContractError("VERIFICATION_UNSUPPORTED","verifier","join key/ordinal differential coverage is not registered")
        for index,nonempty,empty in ((9,left,right),(10,right,left)):
            if nonempty.type.max_items:
                if validate_only:
                    if not bindings_list[index][nonempty.name] or bindings_list[index][empty.name]:
                        raise ContractError("VERIFICATION_BUDGET","verifier","bilateral empty control erased",goal.id)
                else:
                    rows=[_nonnull(nonempty.type.item,3,contract.inputs.index(nonempty))]
                    _ordinalize(nonempty,rows)
                    bindings_list[index][nonempty.name]=rows;bindings_list[index][empty.name]=[]
                coverage.append({"control":goal.id+":only_nonempty:"+nonempty.name,"case":index})
            else: coverage.append({"control":goal.id+":only_nonempty:"+nonempty.name,"domain_inapplicable":"max_items=0"})
        if not left.type.max_items or not right.type.max_items: continue
        lt,rt=left.type.item.field(lk),right.type.item.field(rk)
        if lt.kind==rt.kind=="Int":
            lo,hi=max(lt.low,rt.low),min(lt.high,rt.high)
            common=lo if lo<=hi else None
        else: common=next((v for v in _values(lt) if accepts(v,rt,domain=True)),None)
        controls=[]
        if common is not None:
            controls.append(("match",[common],[common]))
            if left.type.max_items>=2 and right.type.max_items>=2:
                controls.append(("multiplicity",[common,common],[common,common]))
        else: coverage.append({"control":goal.id+":match","domain_inapplicable":"disjoint key domains"})
        unequal=next(((a,b) for a in _values(lt) for b in _values(rt) if a!=b),None)
        if unequal is not None: controls.append(("nonmatch",[unequal[0]],[unequal[1]]))
        else: coverage.append({"control":goal.id+":nonmatch","domain_inapplicable":"both key domains are the same singleton"})
        for label,lv,rv in controls:
            def present(bindings):
                lrows,rrows=bindings[left.name],bindings[right.name]
                if label=="nonmatch": return bool(lrows and rrows) and not any(l[lk]==r[rk] for l in lrows for r in rrows)
                if label=="match": return any(l[lk]==r[rk] for l in lrows for r in rrows)
                return any(sum(l[lk]==v for l in lrows)>=2 and sum(r[rk]==v for r in rrows)>=2 for v in lv)
            found=next((i for i,b in enumerate(bindings_list) if present(b)),None)
            if found is None and validate_only:
                raise ContractError("VERIFICATION_BUDGET","verifier","final packing erased a join control",goal.id+":"+label)
            if found is None:
                for index in (7,8,11,2,3,4,6,1):
                    trial=copy.deepcopy(bindings_list[index])
                    if label=="nonmatch":
                        if index!=8: continue
                        # Case 8 has no unique baseline obligation. Dedicated
                        # unequal keys avoid accidental matches in extra rows.
                        trial[left.name]=[];trial[right.name]=[]
                    for binding,key,values in ((left,lk,lv),(right,rk,rv)):
                        rows=trial[binding.name]
                        for value in values:
                            row=_nonnull(binding.type.item,3,contract.inputs.index(binding));row[key]=value;rows.append(row)
                        if len(rows)>binding.type.max_items: break
                        _ordinalize(binding,rows)
                    else:
                        if present(trial): bindings_list[index]=trial;found=index;break
            if found is None:
                raise ContractError("VERIFICATION_BUDGET","verifier","join match/nonmatch/multiplicity controls do not fit preserved baseline",goal.id+":"+label)
            coverage.append({"control":goal.id+":"+label,"case":found})
    # Recheck after all additions: a later control must not erase an earlier
    # requirement. Row controls only append; bilateral controls reserve 9/10.
    return coverage


def _final_binding_controls(contract,bindings_list,budget,validate_only=False):
    """Require counterexamples at the returned value, including reductions.

    Diagnostic variants never go to lowering or the raw reader. They substitute
    bindings in frozen desired relations; no emitted source or gold is consulted.
    """
    variants=[]; by_name={b.name:b for b in contract.inputs}
    for goal in contract.goals:
        if goal.kind!="filter": continue
        binding=by_name[goal.inputs[0]];item=binding.type.item
        if item.kind!="Record" or binding.type.max_items==0: continue
        fields=sorted({a.get("field","") for a in _atoms(goal.config["predicate"],budget)}-{ "" })
        for field in fields:
            t=item.field(field);t=t.item if t.kind=="Nullable" else t
            for peer,pt in item.fields:
                pt=pt.item if pt.kind=="Nullable" else pt
                if peer in (field,binding.ordinal) or t.kind!=pt.kind: continue
                cfg=copy.deepcopy(goal.config)
                def rename(p):
                    if p["op"] in ("and","or","not"):
                        for child in p["args"]: rename(child)
                    elif p.get("field","")==field:p["field"]=peer
                rename(cfg["predicate"])
                goals=tuple(replace(g,config_json=canonical(cfg)) if g.id==goal.id else g for g in contract.goals)
                variants.append((goal.id+":final_field:"+field+":"+peer,replace(contract,goals=goals),binding.name))
    collections=[b for b in contract.inputs if b.type.kind in ("Seq","Relation")]
    for old in collections:
        for new in collections:
            if old.name==new.name or not shape_equal(old.type,new.type):continue
            if not any(old.name in g.inputs for g in contract.goals):continue
            goals=tuple(replace(g,inputs=tuple(new.name if n==old.name else n for n in g.inputs)) for g in contract.goals)
            variants.append(("final_input:"+old.name+":"+new.name,replace(contract,goals=goals),old.name))
    def different(variant,bindings):
        return not same_value(interpret(contract,bindings,budget),interpret(variant,bindings,budget))
    reserved=iter((1,7,11))
    for label,variant,name in variants:
        if any(different(variant,b) for b in bindings_list):continue
        if validate_only:raise ContractError("VERIFICATION_BUDGET","verifier","final binding contrast erased",label)
        # A singleton makes count/sum cancellation impossible when the filter
        # itself affects the returned value. Keep empty/order/duplicate/bounds
        # baseline cases 0/2/3/4/5/6/9/10 intact.
        found=False
        for bindings in bindings_list:
            for row in list(bindings[name]):
                trial=copy.deepcopy(bindings);trial[name]=[copy.deepcopy(row)]
                _ordinalize(by_name[name],trial[name])
                if different(variant,trial):
                    index=next(reserved,None)
                    if index is None:raise ContractError("VERIFICATION_BUDGET","verifier","final-output binding controls exceed 12-case packing",label)
                    bindings_list[index]=trial;found=True;break
            if found:break
        if not found:raise ContractError("VERIFICATION_UNSUPPORTED","verifier","returned-value binding contrast was not established",label)
    coverage=[]
    for label,variant,name in variants:
        index=next((i for i,b in enumerate(bindings_list) if different(variant,b)),None)
        if index is None:raise ContractError("VERIFICATION_BUDGET","verifier","later witness erased a final binding contrast",label)
        coverage.append({"control":label,"case":index,"returned_value_distinguished":True})
    return coverage


def select_witnesses(contract,budget):
    """12-case baseline plus explicitly checked requirement-derived controls."""
    source_symbols={binding.name for binding in contract.inputs}
    for goal in contract.goals:
        budget.charge("verifier",location="boundary coverage support")
        if goal.kind=="filter" and goal.inputs[0] not in source_symbols:
            raise ContractError("VERIFICATION_UNSUPPORTED","verifier",
                "independent boundary witnesses for intermediate-value predicates are not implemented; candidate is held")
    selections=[];bindings_list=[]
    lengths=(0,1,5,3,5,4,7,2,3,0,4,8)
    for case_index,length in enumerate(lengths):
        bindings={}
        for input_index,binding in enumerate(contract.inputs):
            budget.charge("verifier",location="witness binding")
            typ=binding.type
            if typ.kind in ("Seq","Relation"):
                n=min(length,typ.max_items)
                if input_index==0 and case_index==10 or input_index==1 and case_index==9: n=0
                if input_index==0 and case_index==9 and len(contract.inputs)>1: n=min(1,typ.max_items)
                rows=[_sample(typ.item,j+case_index,input_index) for j in range(n)]
                if case_index==4: rows.reverse()
                if case_index==5 and rows: rows=[copy.deepcopy(rows[0]) for _ in rows]
                if binding.ordinal:
                    for j,row in enumerate(rows): row[binding.ordinal]=j+1
                bindings[binding.name]=rows
            else: bindings[binding.name]=_sample(typ,case_index+input_index)
        if case_index==3:
            # Below/equal/above every directly bound numeric comparison. The
            # unrelated fields remain asymmetric; parameter values come from
            # this caller, never a guessed or embedded threshold.
            for binding in contract.inputs:
                if binding.type.kind not in ("Seq","Relation"): continue
                rows=[]; item=binding.type.item
                def atoms(p):
                    budget.charge("verifier",location="comparison boundary selection")
                    if p["op"] in ("and","or","not"):
                        for child in p["args"]: yield from atoms(child)
                    else: yield p
                for goal in contract.goals:
                    budget.charge("verifier",location="boundary source binding")
                    if goal.kind!="filter" or goal.inputs!=(binding.name,): continue
                    for atom in atoms(goal.config["predicate"]):
                        if atom["op"] not in ("eq","ne","lt","le","gt","ge"): continue
                        threshold=_operand(atom.get("value"),bindings)
                        field=atom.get("field","")
                        typ=item.field(field) if field else item
                        typ=typ.item if typ.kind=="Nullable" else typ
                        if typ.kind!="Int" or type(threshold) is not int: continue
                        for number in (threshold-1,threshold,threshold+1):
                            budget.charge("verifier",location="literal/parameter boundary")
                            if not typ.low<=number<=typ.high: continue
                            row=_sample(item,len(rows)+3)
                            if field: row[field]=number
                            else: row=number
                            rows.append(row)
                if rows:
                    if len(rows)>binding.type.max_items:
                        raise ContractError("VERIFICATION_BUDGET","verifier","required comparison boundaries exceed this witness input domain")
                    bindings[binding.name]=rows
        bindings_list.append(bindings)
    coverage=_required_controls(contract,bindings_list,budget)
    coverage+=_final_binding_controls(contract,bindings_list,budget)
    # Re-establish row/bilateral controls after singleton packing, and then
    # check every final contrast again; additions may cancel count differences.
    coverage=_required_controls(contract,bindings_list,budget)
    coverage+=_final_binding_controls(contract,bindings_list,budget)
    coverage=_required_controls(contract,bindings_list,budget,validate_only=True)
    coverage+=_final_binding_controls(contract,bindings_list,budget,validate_only=True)
    if len(bindings_list)>budget.limits["witnesses"]:
        raise ContractError("VERIFICATION_BUDGET","verifier","required witness count exceeds registered limit")
    for case_index,bindings in enumerate(bindings_list):
        for binding in contract.inputs:
            if not accepts(bindings[binding.name],binding.type,domain=True):
                raise ContractError("VERIFICATION_FAILED","verifier","witness violates declared input domain",binding.name)
        args=[bindings[n] for n in contract.interface.parameters if n not in contract.interface.keyword_only]
        kwargs={n:bindings[n] for n in contract.interface.keyword_only}
        case={"args":args,"kwargs":kwargs}
        if contract.profile=="posix_numeric_stream_v1":
            collection=next(x for x in contract.inputs if x.type.kind in ("Seq","Relation"))
            case={"stdin":"".join(str(v)+"\n" for v in bindings[collection.name]),"argv":[str(bindings[n]) for n in contract.interface.argv]}
        elif contract.profile=="sqlite_select_v1":
            tables={}
            for binding in contract.inputs:
                schema=[]
                for name,t in binding.type.item.fields:
                    base=t.item if t.kind=="Nullable" else t
                    schema.append({"name":name,"type":"TEXT" if base.kind=="Text" else "REAL" if base.kind=="Float64" else "INTEGER","nullable":t.kind=="Nullable"})
                tables[binding.name]={"schema":schema,"rows":[[row[name] for name,t in binding.type.item.fields] for row in bindings[binding.name]]}
            case={"tables":tables}
        case["witness_controls"]=[c for c in coverage if c.get("case")==case_index or "domain_inapplicable" in c and case_index==0]
        selections.append((case,bindings))
    return selections


def _static(source,ledger,contract,plan,artifact,budget):
    def require(ok,message):
        budget.charge("verifier",location=message)
        if not ok: raise ContractError("VERIFICATION_FAILED","verifier",message)
    require(source.hash==ledger.source_hash==contract.source_hash,"source identity")
    require(ledger.hash==contract.ledger_hash,"frozen ledger identity")
    require(not ledger.unknown and not ledger.alternatives,"no unread requirements or unresolved interpretations")
    ids=[r.id for r in ledger.requirements]
    require(len(ids)==len(set(ids)) and set(ids)==set(contract.requirement_ids)==set(plan.discharged),"all requirement identities")
    for r in ledger.requirements:
        require(r.state=="interpreted" and r.spans and all(s.valid(source.raw) for s in r.spans),"valid interpreted source spans")
        p=r.payload
        if r.kind=="interface":
            require(p["name"]==contract.interface.name and tuple(p["parameters"])==contract.interface.parameters and tuple(p.get("keyword_only",()))==contract.interface.keyword_only and tuple(p.get("columns",()))==contract.interface.columns and tuple(p.get("argv",()))==contract.interface.argv,"requested interface binding")
        elif r.kind=="domain":
            b=next((x for x in contract.inputs if x.name==r.target),None)
            require(b is not None and canonical(b.type)==canonical(p["type"]) and b.ordinal==p.get("ordinal",""),"requested input domain binding")
        elif r.kind=="relation":
            g=next((g for g in contract.goals if g.output==p["output"]),None)
            expected_config=copy.deepcopy(p["config"])
            if g:
                for empty_requirement in ledger.requirements:
                    budget.charge("verifier",location="empty-policy provenance")
                    if empty_requirement.kind=="aggregate_empty" and empty_requirement.payload["goal_id"]==g.id:
                        expected_config["empty"]=empty_requirement.payload["value"]
            require(g is not None and g.kind==p["kind"] and g.inputs==tuple(p["inputs"]) and canonical(g.config)==canonical(expected_config) and r.id in g.requirement_ids,"required relation binding")
        elif r.kind=="return": require(p["symbol"]==contract.return_symbol,"required return symbol")
        elif r.kind=="effect": require(p["effect"]==contract.effect,"required input effect")
        elif r.kind=="profile": require(p["profile"]==contract.profile,"required backend profile")
        elif r.kind=="aggregate_empty":
            g=next((g for g in contract.goals if g.id==p["goal_id"]),None)
            require(g is not None and "empty" in g.config and same_value(g.config["empty"],p["value"]),"aggregate empty trigger and value")
        elif r.kind=="input_empty":
            require(any(b.trigger=="input_empty" and b.symbol==r.target and b.requirement_id==r.id and same_value(b.value,p["value"]) for b in contract.boundaries),"entry empty trigger and value")
        elif r.kind!="quoted_material":
            require(False,"unregistered requirement kind")
    require(contract.hash==plan.contract_hash and plan.hash==artifact.plan_hash,"plan and artifact identity")
    require(contract.profile==plan.profile==artifact.profile and artifact.interface==contract.interface,"artifact backend/interface identity")
    require(plan.return_symbol==contract.return_symbol and refines(plan.return_type,contract.return_type),"return type/shape and range identity")
    require(plan.boundaries==contract.boundaries,"boundary preservation")
    require(len(contract.boundaries)==sum(r.kind=="input_empty" for r in ledger.requirements) and all(b.trigger=="input_empty" for b in contract.boundaries),"no unsourced boundary")
    env={b.name:b.type for b in contract.inputs}; goals={g.id:g for g in contract.goals}
    require(len(plan.nodes)==len(goals),"all desired relations have a plan node")
    for n in plan.nodes:
        g=goals.get(n.id)
        require(g is not None and (n.kind,n.inputs,n.output,n.config_json,n.requirement_ids)==(g.kind,g.inputs,g.output,g.config_json,g.requirement_ids),"plan law binds frozen relation")
        require(all(name in env for name in n.inputs),"plan dependencies exist")
        require(n.input_types==tuple(env[name] for name in n.inputs),"plan input types")
        inferred=infer_goal(g,n.input_types,env,contract.profile,_VerifierAccount(budget))
        require(n.output_type==inferred and n.part==PARTS[n.kind] and n.law=="contract-laws-v1:"+n.kind,"independent typed law check")
        require(n.output not in env,"no overwritten symbol")
        env[n.output]=inferred
    require(boundary_type(env.get(plan.return_symbol,ValueType("Unknown")),contract.boundaries)==plan.return_type,"bound artifact return type")


def verify(source,ledger,contract,plan,artifact,budget=None):
    budget=budget or Budget()
    _static(source,ledger,contract,plan,artifact,budget)
    selections=select_witnesses(contract,budget)
    expected=[interpret(contract,bindings,budget) for case,bindings in selections]
    if not all(accepts(value,contract.return_type) for value in expected):
        raise ContractError("VERIFICATION_FAILED","verifier","contract semantic witnesses disagree with declared output type")
    budget.charge("dynamic_artifacts")
    remaining=min(200,budget.remaining_ms())
    # The OS runner receives the public absolute deadline separately from
    # external cancellation, so a timeout does not masquerade as CANCELLED.
    cancelled=budget.cancelled
    observations=run_artifact(contract.profile,artifact.source,contract.interface.runner_dict(),[case for case,bindings in selections],timeout_ms=remaining,cancel=cancelled,
        before_launch=lambda:budget.charge("subprocesses",location="OS probe or witness launch"),
        before_case=lambda:budget.charge("witnesses",location="independent input call permission"),
        before_output=budget.charge_output,after_output=budget.record_output,
        deadline=budget.deadline,cleanup_reserve_ms=50)
    base={"source_hash":source.hash,"ledger_hash":ledger.hash,"contract_hash":contract.hash,"plan_hash":plan.hash,
          "artifact_sha256":artifact.hash,"origin":contract.origin,"domain":asdict(contract)["inputs"],
          "claim":"source-bound typed laws and finite execution witnesses; no universal or raw-language correctness proof",
          "raw_reading_independently_scored":False,"requirements":[{"id":r.id,"span_linked":True,"interpreted":True,"contract_bound":True,"plan_discharged":True,"artifact_checked":False} for r in ledger.requirements],
          "execution":observations}
    isolation=observations.get("isolation",{})
    boundary_checks=isolation.get("checks",{})
    def cleanup_complete(value):
        keys={"group_signalled","leader_reaped","group_absence_confirmed","cleanup_error","deadline_exceeded"}
        return (isinstance(value,dict) and keys.issubset(value)
                and type(value.get("group_signalled")) is bool
                and value.get("leader_reaped") is True and value.get("group_absence_confirmed") is True
                and value.get("cleanup_error") is None and value.get("deadline_exceeded") is False)
    children=observations.get("stats",{}).get("children")
    cleanup_confirmed=(type(children) is list and bool(children)
                       and all(isinstance(child,dict) and cleanup_complete(child.get("cleanup")) for child in children)
                       and cleanup_complete(isolation.get("probe_cleanup")))
    security_complete=(isolation.get("verified") is True
        and isolation.get("fork_denied") is True
        and isolation.get("descendant_scope")=="owned new-session PGID; process-fork denial observed by trusted probe"
        and all(boundary_checks.get(key) is True for key in ("external_read","external_write","local_write","network","unlisted_exec","fork_denied"))
        and cleanup_confirmed)
    if observations.get("status") in ("REQUEST_TIMEOUT","INTERRUPTED","CHILD_TIMEOUT","OUTPUT_LIMIT"):
        budget.stop_execution(observations["status"],"safe execution stopped",observations.get("stats",{}))
    stats=observations.get("stats",{})
    reported_output=budget.report()["resource_usage"]["child_output_bytes"]
    counts_complete=(stats.get("cases_reserved")==budget.used["witnesses"]==len(selections)
                     and stats.get("cases_attempted")==stats.get("cases_finished")==len(selections)
                     and stats.get("unconfirmed_starts")==0)
    bytes_complete=(stats.get("output_bytes")==reported_output["actual_total"]
                    and stats.get("output_reserved_bytes")==reported_output["reserved_total"])
    if observations.get("artifact_sha256")!=artifact.hash or observations.get("status")!="EXECUTED" or not security_complete:
        reason=observations.get("status","VERIFICATION_FAILED")
        if reason=="EXECUTED":
            reason="EXECUTION_INCOMPLETE" if not cleanup_confirmed else "SANDBOX_UNAVAILABLE" if not security_complete else "VERIFICATION_FAILED"
        raise ContractError(reason,"execution","safe execution or its mandatory observations did not complete",base)
    if not counts_complete or not bytes_complete:
        raise ContractError("VERIFICATION_FAILED","execution","logical calls or output bytes were not independently accounted",base)
    results=observations.get("results",[])
    if len(results)!=len(expected):
        raise ContractError("VERIFICATION_FAILED","execution","unexecuted witness remains",base)
    checks=[]
    for index,(actual,want) in enumerate(zip(results,expected)):
        budget.charge("verifier",location="artifact witness result")
        mandatory={"status","exit_code","stdout","stderr","index","cleanup"}
        if contract.profile in ("python_pure_v1","node_commonjs_sync_v1"): mandatory.update(("typed_value","signature","signature_matches","value","process_stderr","mutation"))
        elif contract.profile=="sqlite_select_v1": mandatory.update(("rows","columns","row_types","schema_matches","process_stderr","sqlite_version"))
        else: mandatory.add("protocol")
        ok=mandatory.issubset(actual) and actual.get("index")==index and actual.get("status")=="EXECUTED" and actual.get("exit_code")==0 and cleanup_complete(actual.get("cleanup")) and actual.get("stderr")=="" and ("process_stderr" not in mandatory or actual.get("process_stderr")=="")
        if not cleanup_complete(actual.get("cleanup")):
            raise ContractError("EXECUTION_INCOMPLETE","execution","per-case cleanup was not confirmed",base)
        if contract.profile in ("python_pure_v1","node_commonjs_sync_v1"):
            ok=ok and actual.get("signature_matches") is True and actual.get("mutation",{}).get("unchanged") is True and not actual.get("stdout") and same_value(actual.get("value"),want,js=contract.profile=="node_commonjs_sync_v1")
            if contract.profile=="python_pure_v1": ok=ok and accepts(actual.get("value"),contract.return_type)
            else:
                def no_invalid(t):
                    if t.get("type") in ("undefined","unsupported","nonfinite_number","bool","boolean"): return False
                    return all(no_invalid(child) for child in t.get("items",[])) and all(no_invalid(child) for child in t.get("fields",{}).values())
                ok=ok and no_invalid(actual.get("typed_value",{}))
        elif contract.profile=="sqlite_select_v1":
            wanted_rows=[[row[name] for name in contract.interface.columns] for row in want]
            rows=actual.get("rows",[])
            tag=lambda value: "null" if value is None else "integer" if type(value) is int else "real" if type(value) is float else "text" if type(value) is str else "unsupported"
            ok=ok and actual.get("sqlite_version")=="3.53.2" and actual.get("row_types")==[[tag(value) for value in row] for row in rows]
            if not contract.interface.ordered:
                rows=sorted(rows,key=canonical); wanted_rows=sorted(wanted_rows,key=canonical)
            ok=ok and actual.get("columns")==list(contract.interface.columns) and same_value(rows,wanted_rows)
        else:
            token=lambda v: "null" if v is None else repr(v) if type(v) is float else str(v)
            wanted="".join(token(v)+"\n" for v in want) if isinstance(want,list) else token(want)+"\n"
            # Float64 tokens may differ while round-tripping to the identical value.
            if type(want) is float:
                try: protocol_ok=float(actual.get("stdout",""))==want and actual["stdout"].endswith("\n") and len(actual["stdout"].splitlines())==1
                except ValueError: protocol_ok=False
            else: protocol_ok=actual.get("stdout")==wanted
            ok=ok and protocol_ok
        checks.append({"index":index,"passed":bool(ok),"expected_sha256":digest(want),"case_sha256":digest(selections[index][0])})
        if not ok:
            base["checks"]=checks
            raise ContractError("VERIFICATION_FAILED","verifier","artifact violates interface/effect/value/protocol witness",base)
    for requirement in base["requirements"]: requirement["artifact_checked"]=True
    base.update(status="finite_verified",checks=checks,witness_count=len(checks),universal_proof=False)
    budget.check("verification certificate")
    return base
