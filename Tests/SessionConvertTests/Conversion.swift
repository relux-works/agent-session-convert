import Foundation
import Testing

private let cli = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
    .deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("agent-session-convert")
private let providers = ["claude", "codex", "muse"]

private func run(_ args: [String]) throws -> Int32 {
    let process = Process()
    process.executableURL = cli
    process.arguments = args
    process.standardOutput = FileHandle.nullDevice
    try process.run()
    process.waitUntilExit()
    return process.terminationStatus
}

// Each source is captured once and removed. Independent projection processes must preserve both
// visible messages in order and keep the reasoning sentinel out of all three target transcripts.
@Test(arguments: providers) func independentProjection(sourceProvider: String) throws {
    let dir = URL(fileURLWithPath: ProcessInfo.processInfo.environment["TMPDIR"] ?? NSTemporaryDirectory()).appendingPathComponent(UUID().uuidString)
    try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
    defer { try? FileManager.default.removeItem(at: dir) }
    let src = dir.appendingPathComponent("source.jsonl"), bundle = dir.appendingPathComponent("ir")
    let fixture = cli.deletingLastPathComponent().appendingPathComponent("fixtures/\(sourceProvider).jsonl")
    try FileManager.default.copyItem(at: fixture, to: src)
    try #require(run(["capture", "--from", sourceProvider, "--source-log", src.path, "--out-dir", bundle.path]) == 0)
    try FileManager.default.removeItem(at: src)
    for target in providers {
        let out = dir.appendingPathComponent(target)
        let args = ["project", "--bundle", bundle.path, "--to", target, "--workspace", dir.path, "--out-dir", out.path]
        try #require(run(args) == 0)
        let log = out.appendingPathComponent("session.jsonl")
        let records = try String(contentsOf: log, encoding: .utf8)
        let first = try #require(records.range(of: "juniper-749"))
        let second = try #require(records.range(of: "I have recorded the word."))
        #expect(first.lowerBound < second.lowerBound)
        #expect(!records.contains("private-fixture"))
        // An existing projection is create-only, including when a caller retries.
        #expect(try run(args) != 0)
        #expect(try String(contentsOf: log, encoding: .utf8) == records)
    }
    // Replacing a canonical event must fail before any projected transcript is staged.
    try "{}\n".write(to: bundle.appendingPathComponent("events.jsonl"), atomically: true, encoding: .utf8)
    let bad = dir.appendingPathComponent("bad")
    #expect(try run(["project", "--bundle", bundle.path, "--to", "muse", "--workspace", dir.path, "--out-dir", bad.path]) != 0)
    #expect(!FileManager.default.fileExists(atPath: bad.appendingPathComponent("session.jsonl").path))
}

// A fork's abandoned answer remains recoverable in the snapshot and must not enter the active
// continuation. An oversized answer must keep every byte through detached blob projection.
@Test func branchAndLargePayload() throws {
    let dir = URL(fileURLWithPath: ProcessInfo.processInfo.environment["TMPDIR"] ?? NSTemporaryDirectory())
        .appendingPathComponent(UUID().uuidString)
    try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
    defer { try? FileManager.default.removeItem(at: dir) }
    let value = String(repeating: "石", count: 30_000)
    let input = """
    {"type":"user","sessionId":"sample","uuid":"u","parentUuid":null,"message":{"content":"question"}}
    {"type":"assistant","sessionId":"sample","uuid":"a","parentUuid":"u","message":{"content":"abandoned-branch"}}
    {"type":"assistant","sessionId":"sample","uuid":"b","parentUuid":"u","message":{"content":"\(value)"}}
    """
    let src = dir.appendingPathComponent("source")
    try input.write(to: src, atomically: true, encoding: .utf8)
    let bundle = dir.appendingPathComponent("bundle")
    try #require(run(["convert", "--from", "claude", "--to", "codex", "--source-log", src.path,
                      "--workspace", dir.path, "--out-dir", bundle.path]) == 0)
    let staged = try String(contentsOf: bundle.appendingPathComponent("projection/session.jsonl"), encoding: .utf8)
    #expect(staged.contains(value))
    #expect(!staged.contains("abandoned-branch"))
    let ir = try String(contentsOf: bundle.appendingPathComponent("events.jsonl"), encoding: .utf8)
    #expect(ir.contains("text_blob"))
    #expect(!ir.contains(value))
    let blobs = try FileManager.default.contentsOfDirectory(at: bundle.appendingPathComponent("blobs"), includingPropertiesForKeys: nil)
    let blob = try #require(blobs.first)
    try "corrupt".write(to: blob, atomically: true, encoding: .utf8)
    #expect(try run(["project", "--bundle", bundle.path, "--to", "claude", "--workspace", dir.path,
                     "--out-dir", dir.appendingPathComponent("failed").path]) != 0)
}

// Claude may put results of parallel calls on sibling UUIDs. Replay must retain both linked
// outputs while still keeping a historical tool operation inert on the target.
@Test func parallelResults() throws {
    let dir = URL(fileURLWithPath: ProcessInfo.processInfo.environment["TMPDIR"] ?? NSTemporaryDirectory())
        .appendingPathComponent(UUID().uuidString)
    try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
    defer { try? FileManager.default.removeItem(at: dir) }
    let input = """
    {"type":"user","sessionId":"s","uuid":"u","parentUuid":null,"message":{"content":"read both"}}
    {"type":"assistant","sessionId":"s","uuid":"a","parentUuid":"u","message":{"content":[{"type":"tool_use","id":"one","name":"read","input":{}},{"type":"tool_use","id":"two","name":"read","input":{}}]}}
    {"type":"user","sessionId":"s","uuid":"r1","parentUuid":"a","message":{"content":[{"type":"tool_result","tool_use_id":"one","content":"first-output"}]}}
    {"type":"user","sessionId":"s","uuid":"r2","parentUuid":"a","message":{"content":[{"type":"tool_result","tool_use_id":"two","content":"second-output"}]}}
    """
    let src = dir.appendingPathComponent("log"), bundle = dir.appendingPathComponent("bundle")
    try input.write(to: src, atomically: true, encoding: .utf8)
    try #require(run(["convert", "--from", "claude", "--to", "codex", "--source-log", src.path,
                      "--workspace", dir.path, "--out-dir", bundle.path]) == 0)
    let output = try String(contentsOf: bundle.appendingPathComponent("projection/session.jsonl"), encoding: .utf8)
    #expect(output.contains("[tool result] first-output"))
    #expect(output.contains("[tool result] second-output"))
    #expect(!output.contains("\"function_call\""))
}
