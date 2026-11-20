import Foundation
import Testing

// The provider may acknowledge a fork while exposing different UI history, model history or
// account ownership. Only a matching, provider-owned result can produce a published receipt.
// A missing login must stop before the fork request.
@Test(arguments: ["valid", "ui-mismatch", "model-mismatch", "unowned", "logged-out"])
func codexReadback(mode: String) throws {
    let base = URL(fileURLWithPath: ProcessInfo.processInfo.environment["TMPDIR"] ?? NSTemporaryDirectory())
        .appendingPathComponent(UUID().uuidString)
    let fm = FileManager.default
    try fm.createDirectory(at: base, withIntermediateDirectories: true)
    defer { try? fm.removeItem(at: base) }
    let repo = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
        .deletingLastPathComponent().deletingLastPathComponent()
    let provider = base.appendingPathComponent("codex")
    let fake = #"""
    #!/usr/bin/env python3
    import json, os, sys
    from pathlib import Path
    mode = os.environ["CASE"]
    for line in sys.stdin:
        r = json.loads(line)
        method = r["method"]
        if method == "initialized":
            continue
        if method == "initialize":
            result = {}
        if method == "account/read":
            result = {"account": None if mode == "logged-out" else {"type": "chatgpt"}}
        if method == "thread/fork":
            Path("called").touch()
            sid = "018f0000-0000-7000-a000-000000000001"
            path = Path(os.environ["CODEX_HOME"]) / "sessions" / ("rollout-" + sid + ".jsonl")
            path.parent.mkdir(parents=True)
            cwd = os.getcwd()
            meta = {"id": sid, "cwd": cwd, "account_scoped": mode != "unowned"}
            msg = {"type": "message", "role": "user", "content": [
                {"type": "input_text", "text": "wrong" if mode == "model-mismatch" else "marker"}]}
            path.write_text(json.dumps({"type":"session_meta","payload":meta}) + "\n" +
                            json.dumps({"type":"response_item","payload":msg}) + "\n")
            item = {"type":"userMessage","content":[{"type":"text","text":"marker"}]}
            result = {"thread":{"id":sid,"cwd":cwd,"path":str(path),"turns":[
                {"items":[] if mode == "ui-mismatch" else [item]}]}}
        print(json.dumps({"id": r["id"], "result": result}), flush=True)
    """#
    try fake.write(to: provider, atomically: true, encoding: .utf8)
    try fm.setAttributes([.posixPermissions: 0o755], ofItemAtPath: provider.path)
    let p = Process()
    p.executableURL = URL(fileURLWithPath: "/usr/bin/env")
    p.arguments = ["python3", "-c", """
        from pathlib import Path
        from session_convert.codex_import import publish_fork
        p = Path.cwd()
        publish_fork(p / "staged.jsonl", p, [("user", "marker")], {"target_id":"stage"})
        """]
    p.currentDirectoryURL = base
    var env = ProcessInfo.processInfo.environment
    env["PATH"] = base.path + ":" + (env["PATH"] ?? "")
    env["CASE"] = mode
    env["CODEX_HOME"] = base.appendingPathComponent("store").path
    env["PYTHONPATH"] = repo.path
    p.environment = env
    p.standardError = FileHandle.nullDevice
    try p.run()
    p.waitUntilExit()
    #expect((p.terminationStatus == 0) == (mode == "valid"))
    #expect(fm.fileExists(atPath: base.appendingPathComponent("called").path) == (mode != "logged-out"))
    if mode != "logged-out" {
        let receipt = try JSONSerialization.jsonObject(with: Data(contentsOf: base.appendingPathComponent("validation.json"))) as? [String: Any]
        #expect(receipt?["state"] as? String == (mode == "valid" ? "published" : "created_pending_readback"))
    }
}
