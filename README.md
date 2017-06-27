# GitHubFlow
__Automated Git-Flow release handling__

There are several great CLI and IDE tools for [GitFlow](https://datasift.github.io/gitflow/IntroducingGitFlow.html), but most of them cannot coexist with GitHub's branch protection active on the master branch.

__GitHubFlow__ is intended to slot integrate with a locked-down GitHub project, taking care of mundane tasks. Currently, it handles:
* Ensuring pull requests against master are include the information neccessary for creating a release.
    - Well... It checks the PR title is a valid version token, for now.
* Creates a release whenever a PR against master is merged, converting the PR body to release notes.
* Optionally approves release PR's if they appear to be valid.
    - In projects where both dev and master are protected, a PR against master should only ever include code that was already peer-reviewed.
