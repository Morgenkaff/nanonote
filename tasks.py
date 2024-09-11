import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

from pathlib import Path
from tempfile import NamedTemporaryFile

from invoke import task, run

from changelog import Changelog, Release


ARTIFACTS_DIR = Path("artifacts")

CHANGELOG_MD = Path("CHANGELOG.md")
APPSTREAM_XML = Path("src/linux/nanonote.metainfo.xml")

MAIN_BRANCH = "master"

PREP_RELEASE_BRANCH = "prep-release"


def get_version():
    return os.environ["VERSION"]


def erun(*args, **kwargs):
    """Like run, but with echo on"""
    kwargs["echo"] = True
    return run(*args, **kwargs)


def cerun(c, *args, **kwargs):
    """Like Context.run, but with echo on"""
    kwargs["echo"] = True
    return c.run(*args, **kwargs)


def ask(msg: str) -> str:
    """Show a message, wait for input and returns it"""
    print(msg, end=" ")
    return input()


def is_ok(msg: str) -> bool:
    """Show a message, append (y/n) and return True if user select y or Y"""
    answer = ask(f"{msg} (y/n)").lower()
    return answer == "y"


@task(help={"skip_changelog": "Add skip-changelog label"})
def create_pr(c, skip_changelog=False):
    """Create a pull-request and mark it as auto-mergeable"""
    cmd = "gh pr create --fill"
    if skip_changelog:
        cmd += " --label skip-changelog"
    result = cerun(c, cmd, warn=True)
    if not result:
        sys.exit(1)
    cerun(c, "gh pr merge --auto -dm")


def replace_in_file(path, rx, replacement):
    text = path.read_text()
    text, count = rx.subn(replacement, text)
    if count == 0:
        # Can happen if a command has to be re-run another time
        return
    if count > 1:
        sys.exit(f"Too many replacements in {path}: {count}")
    path.write_text(text)


@task
def update_version(c):
    version = get_version()
    replace_in_file(
        Path("CMakeLists.txt"),
        re.compile(r"^    VERSION .*", flags=re.MULTILINE),
        f"    VERSION {version}"
    )
    replace_in_file(
        Path("nix/flake.nix"),
        re.compile(r'version = "\d+\.\d+\.\d+";'),
        f'version = "{version}";'
    )


@task
def update_appstream_releases(c):
    """Regenerate the <releases> element of our appstream file from
    CHANGELOG.md"""
    changelog = Changelog.from_path(CHANGELOG_MD)

    releases_et = ET.Element("releases")
    for release in changelog.releases.values():
        release_et = ET.SubElement(releases_et, "release",
                                   {
                                       "version": release.version,
                                       "date": release.date
                                   })
        description_et = ET.SubElement(release_et, "description")
        for change_type, changes in release.changes.items():
            p_et = ET.SubElement(description_et, "p")
            p_et.text = change_type
            ul_et = ET.SubElement(description_et, "ul")
            for change in changes:
                li_et = ET.SubElement(ul_et, "li")
                li_et.text = change
    content = ET.tostring(releases_et, encoding="unicode")

    # Replace the <releases> element by hand to avoid loosing comments, if any
    appstream_content = APPSTREAM_XML.read_text()
    appstream_content, count = re.subn("<releases>.*</releases>",
                                       content,
                                       appstream_content, flags=re.DOTALL)
    assert count == 1
    subprocess.run(["xmllint", "--format", "--output", APPSTREAM_XML, "-"],
                   check=True,
                   text=True,
                   input=appstream_content)


@task
def create_release_branch(c):
    version = get_version()
    run(f"gh issue list -m {version}", pty=True)
    run("gh pr list", pty=True)
    if not is_ok("Continue?"):
        sys.exit(1)

    erun(f"git checkout {MAIN_BRANCH}")
    erun("git pull")
    erun("git status -s")
    if not is_ok("Continue?"):
        sys.exit(1)

    create_release_branch2(c)


@task
def create_release_branch2(c):
    version = get_version()
    erun(f"git checkout -b {PREP_RELEASE_BRANCH}")

    update_version(c)

    erun(f"changie batch {version}")
    print(f"Review/edit changelog (.changes/{version}.md)")
    if not is_ok("Looks good?"):
        sys.exit(1)
    erun("changie merge")
    print("Review CHANGELOG.md")

    if not is_ok("Looks good?"):
        sys.exit(1)

    update_appstream_releases(c)


@task
def update_ts(c):
    erun("ninja -C build lupdate")
    erun("git add src/translations")
    erun("git commit -m 'Update translations'")


@task
def commit_push(c):
    version = get_version()
    erun("git add .")
    erun(f'git commit -m "Prepare release of {version}"')
    erun(f"git push -u origin {PREP_RELEASE_BRANCH}")
    create_pr(c)


@task
def tag(c):
    version = get_version()
    erun(f"git checkout {MAIN_BRANCH}")
    erun("git pull")
    changes_file = Path(".changes") / f"{version}.md"
    if not changes_file.exists():
        print(f"{changes_file} does not exist, check previous PR has been merged")
        sys.exit(1)
    if not is_ok("Create tag?"):
        sys.exit(1)

    erun(f"git tag -a {version} -m 'Releasing version {version}'")

    erun(f"git push origin {version}")


def prepare_release_notes(release: Release) -> str:
    """
    Take a Release instance and produce markdown suitable for GitHub release
    notes
    """
    lines = []
    for change_type, changes in release.changes.items():
        lines.append(f"## {change_type}")
        for change in changes:
            lines.append(f"- {change}")
    return "\n\n".join(lines) + "\n"


@task(help={"pre": "This is a prerelease"})
def publish(c, pre=False):
    version = get_version()
    changelog = Changelog.from_path(CHANGELOG_MD)
    release = changelog.releases[version]
    content = prepare_release_notes(release)

    with NamedTemporaryFile() as tmp_file:
        tmp_file.write(content.encode("utf-8"))
        tmp_file.flush()
        cmd = f"gh release edit {version} -F{tmp_file.name} --draft=false"
        if pre:
            cmd += " --prerelease"
        erun(cmd)
