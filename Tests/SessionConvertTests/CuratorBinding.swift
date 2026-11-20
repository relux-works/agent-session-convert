import Foundation
import Testing

// A managed Muse UUID is unique within the selected profile. A conflicting target lock,
// a resolver pointing at the decoy store, or a missing source binding must stop before
// the writer starts, even when the caller has a perfectly usable personal home.
@Test(arguments: ["valid", "duplicate", "wrong-home", "changed-lock", "unbound"])
func curatorDestination(_ mode: String) throws {
    let root = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent(UUID().uuidString)
    let repo = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
        .deletingLastPathComponent().deletingLastPathComponent()
    let fm = FileManager.default
    try fm.createDirectory(at: root, withIntermediateDirectories: true)
    defer { try? fm.removeItem(at: root) }
    let python = #"""
    import json,os,sys
    from pathlib import Path
    from session_convert import binding
    base=Path.cwd().resolve()
    mode=os.environ["BIND_CASE"]
    sid="01111111-1111-7111-8111-111111111111"
    lock="1"*64
    rows=[]
    for profile in ["keeper","another"] if mode=="duplicate" else ["keeper"]:
        for runtime in ["muse","codex_cli"]:
            home=base/profile/runtime
            home.mkdir(parents=True)
            rows.append(dict(home=str(home),environment=runtime,profile=profile,mode="managed-home",provisioned=True))
            (home/".agent-environment.json").write_text(json.dumps(dict(profile=dict(name=profile,lock_sha256=lock))))
            if runtime=="muse":
                log=home/"data/muse/sessions/2026/11/20"/sid/"session.jsonl"
                log.parent.mkdir(parents=True)
                log.touch()
    def resolve(*args):
        if args[0]=="status":
            return {"homes":rows}
        target=base/"keeper/codex_cli"
        return dict(profile=dict(name="keeper",lock_sha256="2"*64 if mode=="changed-lock" else lock),
                    environment="codex_cli",env={"CODEX_HOME":str(base if mode=="wrong-home" else target)})
    binding.curator=resolve
    os.environ["CODEX_HOME"]=str(base/"decoy")
    try:
        found=binding.locate("muse",sid)
        assert Path(found["source_log"])==log
        source=None if mode=="unbound" else found
        d=binding.destination(source,"codex",None,False)
        assert mode=="valid" and d["profile"]=="keeper"
        assert os.environ["CODEX_HOME"]==str(base/"keeper/codex_cli")
        assert binding.resume("codex",sid,d)[:5]==["curator","run","codex_cli","--profile","keeper"]
    except ValueError as e:
        reasons={"duplicate":"missing or ambiguous","wrong-home":"environment mismatch",
                 "changed-lock":"binding mismatch","unbound":"unknown source profile"}
        assert mode in reasons and reasons[mode] in str(e)
        assert os.environ["CODEX_HOME"]==str(base/"decoy")
    assert not (base/"decoy").exists()
    """#
    let p = Process()
    p.executableURL = URL(fileURLWithPath: "/usr/bin/env")
    p.arguments = ["python3", "-c", python]
    p.currentDirectoryURL = root
    var env = ProcessInfo.processInfo.environment
    env["BIND_CASE"] = mode
    env["PYTHONPATH"] = repo.path
    p.environment = env
    try p.run()
    p.waitUntilExit()
    #expect(p.terminationStatus == 0)
}
