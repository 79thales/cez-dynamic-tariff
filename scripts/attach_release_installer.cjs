/* Draft uploads and read-only verification of previously published installers. */
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const crypto = require("node:crypto");
const { execFileSync } = require("node:child_process");

const sha256 = data => `sha256:${crypto.createHash("sha256").update(data).digest("hex")}`;

async function downloadAsset(asset) {
  const response = await fetch(asset.browser_download_url, { signal: AbortSignal.timeout(30000) });
  if (!response.ok) throw new Error(`Cannot verify existing installer: HTTP ${response.status}`);
  return Buffer.from(await response.arrayBuffer());
}

function verifyContents(builtPath, existingData, tag) {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "cez-release-check-"));
  const existingPath = path.join(temporary, "existing.zip");
  try {
    fs.writeFileSync(existingPath, existingData);
    execFileSync("python", ["scripts/verify_release_package.py", "--built", builtPath,
      "--existing", existingPath, "--expected-tag", tag], { stdio: "inherit" });
  } finally {
    if (fs.existsSync(existingPath)) fs.unlinkSync(existingPath);
    fs.rmdirSync(temporary);
  }
}

async function attachInstaller({ github, context, core, tag, directory = "dist",
  download = downloadAsset, verify = verifyContents }) {
  const name = "cez_dynamic_tariff.zip";
  const builtPath = path.join(directory, name);
  const data = fs.readFileSync(builtPath);
  const digest = sha256(data);
  const releases = await github.paginate(github.rest.repos.listReleases, {
    ...context.repo, per_page: 100,
  });
  let release = releases.find(item => item.tag_name === tag);
  if (!release) {
    release = (await github.rest.repos.createRelease({
      ...context.repo, tag_name: tag, name: tag,
      body: fs.readFileSync(path.join(directory, "release-notes.md"), "utf8"),
      draft: true, prerelease: tag.includes("-"),
    })).data;
  }
  const existing = release.assets.find(asset => asset.name === name);
  if (existing) {
    if (existing.state !== "uploaded") throw new Error("Existing installer is not fully uploaded.");
    if (existing.digest !== digest || existing.size !== data.length) {
      const downloaded = await download(existing);
      if (downloaded.length !== existing.size
        || (existing.digest && sha256(downloaded) !== existing.digest)) {
        throw new Error("Downloaded installer failed size or SHA-256 verification.");
      }
      await verify(builtPath, downloaded, tag);
      core.notice("Existing installer contents verified; ZIP metadata or line endings differ. No changes made.");
    } else {
      core.notice("Identical installer already attached; no changes made.");
    }
  } else {
    if (!release.draft) {
      throw new Error("Published release is missing its installer. Refusing to modify published assets.");
    }
    const asset = (await github.rest.repos.uploadReleaseAsset({
      ...context.repo, release_id: release.id, name, data,
      headers: { "content-type": "application/zip" },
    })).data;
    if (asset.state !== "uploaded" || asset.size !== data.length || asset.digest !== digest) {
      throw new Error("Uploaded installer failed size or SHA-256 verification. Keep the release as a draft.");
    }
  }
  await core.summary
    .addHeading(release.draft ? "Installer ready; release is still a draft"
      : "Published installer verified; release unchanged")
    .addLink(tag, release.html_url)
    .addRaw(release.draft
      ? "\nReview release notes and Quality, HACS and Hassfest before publishing.\n"
      : "\nNo assets or release notes were changed; the download count is preserved.\n")
    .write();
  return { published: !release.draft, url: release.html_url };
}

module.exports = { attachInstaller };
