const fs = require("node:fs"), os = require("node:os"), path = require("node:path");
const crypto = require("node:crypto"), assert = require("node:assert/strict"), test = require("node:test");
const { attachInstaller } = require("../scripts/attach_release_installer.cjs");
const digest = data => `sha256:${crypto.createHash("sha256").update(data).digest("hex")}`;
const data = Buffer.from("built installer");
const asset = (buffer = data) => ({ name: "cez_dynamic_tariff.zip", state: "uploaded", size: buffer.length, digest: digest(buffer) });

function fixture(t, releases, options = {}) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "cez-workflow-test-"));
  fs.writeFileSync(path.join(directory, "cez_dynamic_tariff.zip"), data);
  fs.writeFileSync(path.join(directory, "release-notes.md"), "Czech and English notes");
  t.after(() => {
    for (const name of ["cez_dynamic_tariff.zip", "release-notes.md"]) fs.unlinkSync(path.join(directory, name));
    fs.rmdirSync(directory);
  });
  const calls = [], headings = [];
  const summary = { addHeading(value) { headings.push(value); return this; }, addLink() { return this; }, addRaw() { return this; }, async write() {} };
  const args = {
    directory, tag: "v1.0.8", context: { repo: { owner: "example", repo: "tariff" } },
    core: { notice(value) { calls.push(["notice", value]); }, summary },
    github: { async paginate() { return releases; }, rest: { repos: {
      listReleases() {},
      async createRelease(request) { calls.push(["create", request]); return { data: release(true, []) }; },
      async uploadReleaseAsset(request) { calls.push(["upload", request]); return { data: options.badUpload ? { ...asset(), digest: "invalid" } : asset() }; },
    } } },
    async download() { calls.push(["download"]); return options.downloaded; },
    async verify() { calls.push(["verify"]); if (options.changed) throw new Error("Code differs"); },
  };
  return { args, calls, headings, writes: () => calls.filter(call => ["create", "upload"].includes(call[0])) };
}
function release(draft, assets = [asset()]) { return { id: 1, tag_name: "v1.0.8", draft, assets, html_url: "https://github.com/example/tariff/releases/tag/v1.0.8" }; }

test("published identical installer succeeds without writes", async t => {
  const s = fixture(t, [release(false)]);
  const result = await attachInstaller(s.args);
  assert.equal(result.published, true); assert.deepEqual(s.writes(), []);
  assert.match(s.headings[0], /Published installer verified/);
});
test("published legacy installer verifies content and preserves its asset", async t => {
  const old = Buffer.from("old ZIP with matching code");
  const s = fixture(t, [release(false, [asset(old)])], { downloaded: old });
  await attachInstaller(s.args);
  assert.deepEqual(s.writes(), []); assert.ok(s.calls.some(call => call[0] === "verify"));
});
test("different code is rejected without writes", async t => {
  const old = Buffer.from("different code");
  const s = fixture(t, [release(false, [asset(old)])], { downloaded: old, changed: true });
  await assert.rejects(attachInstaller(s.args), /Code differs/); assert.deepEqual(s.writes(), []);
});
test("downloaded bytes must match GitHub asset size and digest", async t => {
  for (const downloaded of [Buffer.from("tampered content"), Buffer.from("other")]) {
    const old = Buffer.from("old ZIP with matching code");
    const s = fixture(t, [release(false, [asset(old)])], { downloaded });
    await assert.rejects(attachInstaller(s.args), /size or SHA-256/);
    assert.deepEqual(s.writes(), []); assert.ok(!s.calls.some(call => call[0] === "verify"));
  }
});
test("published release missing installer fails without uploading", async t => {
  const s = fixture(t, [release(false, [])]);
  await assert.rejects(attachInstaller(s.args), /missing its installer/); assert.deepEqual(s.writes(), []);
});
test("new release creates only a draft and verifies the uploaded digest", async t => {
  const s = fixture(t, []); const result = await attachInstaller(s.args);
  assert.equal(result.published, false); assert.equal(s.writes().length, 2);
  const created = s.calls.find(call => call[0] === "create")[1]; assert.equal(created.draft, true);
  assert.match(s.headings[0], /still a draft/);
});
test("existing draft without installer receives a verified upload", async t => {
  const s = fixture(t, [release(true, [])]); await attachInstaller(s.args);
  assert.equal(s.writes().length, 1); assert.equal(s.writes()[0][0], "upload");
});
test("existing identical draft is left unchanged", async t => {
  const s = fixture(t, [release(true)]); await attachInstaller(s.args); assert.deepEqual(s.writes(), []);
});
test("partial or corrupted uploads are rejected", async t => {
  const partial = fixture(t, [release(false, [{ ...asset(), state: "starter" }])]);
  await assert.rejects(attachInstaller(partial.args), /not fully uploaded/); assert.deepEqual(partial.writes(), []);
  const corrupt = fixture(t, [release(true, [])], { badUpload: true });
  await assert.rejects(attachInstaller(corrupt.args), /Uploaded installer failed/);
});
