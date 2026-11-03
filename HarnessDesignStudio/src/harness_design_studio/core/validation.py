"""What `validate` and `check` look at: the files of a project folder, read the way the editor reads
them, plus the checks that need the whole project. One function, shared by the command line and the
scripting interface (`harness_design_studio.api`), so that they cannot disagree."""

from pathlib import Path

from harness_design_studio.core.io.loader import LoadResult, load_project, non_canonical_files
from harness_design_studio.core.issues import Issue

NOT_CANONICAL = (
    "File differs from the tool's own formatting (hand-edited or merged). "
    "It will be rewritten on the next save."
)


def validate_folder(
    path: Path | str, *, merge_check: bool = False
) -> tuple[LoadResult, list[Issue]]:
    """The loaded project and the issues found after loading it (not yet merged with the issues
    of loading). `merge_check` is what `check` adds to `validate`: files that differ from the
    tool's own formatting and released harnesses that were edited."""
    path = Path(path)
    result = load_project(path)
    extra: list[Issue] = []
    if merge_check:
        if result.project.read_only:
            extra.append(
                Issue(
                    "info", "skipped_canonical_check", "Format check skipped (read-only project)."
                )
            )
        elif not result.project.recovered:
            extra.extend(
                Issue(
                    "warning",
                    "not_canonical",
                    NOT_CANONICAL,
                    rel,
                )
                for rel in non_canonical_files(path, result.project)
            )
    if merge_check and not result.project.recovered:
        from harness_design_studio.core.vcs.consistency import release_integrity

        extra.extend(release_integrity(result.project))
    if not result.project.recovered:
        from harness_design_studio.core import configcheck
        from harness_design_studio.core.verify import link_issues

        extra.extend(link_issues(result.project))  # a harness made from a link must match it
        # a value of config/*.json that is set but cannot be used: the same check as `generate`,
        # `drc` and `config` (D-191); before, `validate` said "0 error(s)" for a value they refuse
        extra.extend(configcheck.validate(result.project))
        if result.project.extensions is not None:  # S8: a broken extension is reported, never fatal
            extra.extend(
                Issue("warning", "extension_problem", i.render(), i.file)
                for i in result.project.extensions.issues
            )
    return result, extra
