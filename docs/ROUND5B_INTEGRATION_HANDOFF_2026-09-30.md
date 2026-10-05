# Round5-B firstfreeze handoff — 2026-09-30

対象は integrate/one-vera、観測 HEAD 8b2732089a133300c365ce332eaf74de2a82fd29。独立コピー b-checkout のみを編集。所有は新規 verantyx/contract_*.py と tests/test_contract_*.py。原checkout、one.py、semantic_*、既存library、コーパス、既存プロセスは変更していない。

## 接続 API

from verantyx.contract_codegen import ContractCodeGenerator, generate_code, is_code_request
ContractCodeGenerator(profile=None).generate(raw, cancel=None) -> dict
または generate_code(raw, profile=None, cancel=None)。profileは利用者が原文/実行設定で選択する場合だけ指定。通常routerはraw intentのis_code_requestで生成要求を判別し、このgenerateを呼ぶ。prototype mode=contractも同じgateを呼ぶ。拒否後のlegacy ANSWER fallbackは禁止。

成功fields: verdict=ANSWER, status=verified, language, profile, code, text, source, ledger, contract, plan, verification, budget, trace。
失敗fields: verdict=typed reason, status=refused/held, code=None, text, source_hash (非text入力はNone), failure={code,stage,message,details}, budget, trace。準備済みsource/ledger/contract/planとexecution certificateも利用可能な時だけ保持する。
Verificationのclaimは source-bound typed laws and finite execution witnesses。rawの独立意味正答・全入力の完全証明を意味しない。検査artifactと返却codeのSHA一致をgateする。compile-only/部分witness/中断/隔離不能からコードを公開しない。

SourceはUnicode半開span、identity normalization、quote/code regionを保持。Ledgerは合成前に固定し、unknown clause/同点/矛盾を落とさない。Goalはnamed inputs/outputの関係を保持。synthesizeは型/lawとdependency graphから未見組合せを構成し、説明順や近傍fieldを計算順・対象にしない。既存code_parts:v1とrewrite_coreの構造束縛を使用。独立sovereignの得点を混ぜない。

Diagnostic API: contract_reader.read_requirements(raw,budget)->source,ledger,contract; contract_plan.synthesize(contract,budget)->plan; contract_lower.lower(contract,plan,budget)->Artifact。gold_contractは独立S/L/V診断のみで、公開raw性能として数えない。

## 支援範囲と未達

四profileにlowering経路あり。登録10familyとsubkindの閉じたlawから構成する。raw readerは明示profile/interface、有限整数/ASCII schema、named intermediate/明示first-then順序、全句照合の保守的文法。通常自然文のR/E coverageは独立80素材で未評価。未知語彙や任意プログラム、async/external I/O/複雑schema等は成功にしない。

中間値のfilter比較には独立boundary witnessの逆像生成がまだなく、VERIFICATION_UNSUPPORTED/held。入力への直接比較はliteral/parameterの下・一致・上をwitnessへ束縛。input-emptyと途中empty、Null/zero/未指定、bool/Int、schema/順序/多重性を分ける。出力unionの一部（Intにinput-empty nullを付ける等）は現実装未達。SQL Relation row sentinelは型/schema/rangeを確認する。

MacのSeatbelt probeは全四profileでchild200ms超過。実OSの6試験は6fail、実行witness0、公開四raw smokeもANSWER0。制限を緩和せずSANDBOX_UNAVAILABLEでholdした。通常ツールsandbox内ではsandbox_apply自体もEPERM。最終sandbox hardeningは静的確認のみ。CPU1s/wall200ms/FSIZE0/CORE0/FD64等を設定、memory512MiBは5ms RSS watchdogであり瞬間値の完全hard capではない。DATA/AS rlimitはこのMacでEINVAL。50ms公開速度線、四profile実OS対応、B採用は未達。load average約274の負荷指示後は新規広域/大量subprocess試験を停止した。

## 保存した検証

coreの構造/意味oracleは17件pass（deterministic clock、公開速度ではない）。lowering手oracle baseline23件pass、後続boundary連動で22pass/SQL1errorを保存し、SQL helper修正後の単一SQL境界テスト1件はpass。sandbox unitは最終22pass、OS integrationは6fail。独立Vレビュー6件は初回redを残し修正後全部pass。source-frozen empty追加、返却range改変、entry trigger改変、必須観測の欠落、direct比較境界、非text/不正UTF8を検査した。これらは実装者self fixtureと独立実装レビューであり、公開B80・封印の成績ではない。

doctorはexit0・failed=[]。指定guard/verify_all.pyは独立snapshotで起動したが停滞し、負荷調整指示に従い自分のsession6435だけSIGINT、exit130。rewrite_kernelの計算中断ログを保存。guard全通過とはしない。原CLI/コーパス/Wiki/他担当は停止していない。

再現: snapshotで /opt/homebrew/bin/python3.11 -m unittest discover -s tests -p test_contract_core.py、test_contract_review.py。各1workerでOS生成コードは実行しない。SQL小確認は -p test_contract_lower.py -k sql_empty_mean_and_entry_override。全lower suite23件は以前36〜42秒、Nodeを複数起動するため親の枠調整まで再起動しない。OS確認は VERA_SANDBOX_INTEGRATION=1 ...test_contract_sandbox.py（6独立profile/probe呼出し、最大200ms/child、現環境で失敗）。公共smokeは b-evidence/public_smoke.py（4raw、各probe1と最大12case；現結果cases0）。guard広域再試験は親の実行枠調整待ち。

## 共有意味基盤・非学習の構造保持

contract_ir.meaning_envelope(source,ledger,contract)はsource・義務span/scope・typed symbols・named relations・effects/boundaries・完全contract payloadをlosslessで提供。A/C adapterが保持できる境界であり、A/Cのschemaや成功を先取りしない。意味理解と自由文生成が基盤、コードはその応用というユーザー優先順位を維持する。今回の合成は登録演算閉包内の新規構成で、閉包外生成/汎用意味/自由文完成ではない。

ユーザーの重みは学習なしのコーパス圧縮/配置/独自構造パラメータ。Bのregistry/hash/型付き辺は非学習だが、コーパス圧縮器や重み全基盤を実装したとは言わない。既存再利用候補はCrossStoreのcore/facet count、store_sqlite.pyのcores/facets/provenance保存、rewrite_kernel.RuleStore、code_ingestのAST十字。本文/出典・条件・否定・訂正・不確実性・world・symbol identityを圧縮時に落とさない。

検証可能な将来codec契約: decode(encode(M))のcanonical意味payload/source hashがMと一致し、各源span/condition/polarity/correction/unknown/identity/effectが復元できること。圧縮symbol ID/registry pointerは配置情報であり、新しい根拠/投票や否定を生まない。登録順・配置・参照IDの置換で意味判定不変、破損参照/同名scope collision/否定脱落はtyped拒否。独立QA/R/Eで意味保持を別測定し、圧縮率だけで成功としない。このcodecと非学習構造parameter検索はB内で未実装、既存コーパス処理は置換していない。

## 残ブロッカー

one.Vera通常router/prototype接続は親所有。実OS隔離/200ms、公開50ms、全counter hook独立監査、runtime版/環境hashcertificate、独立B80 R/S/L/V/E、未知自然文/閉包外/自由文基盤が未完了。原環境manifestはあれば同梱し、初期環境の記録と実動作検証を混同しない。最終4群/Pro/旧sealedは一切読まず実行していない。外部push/deploy/mergeなし。
