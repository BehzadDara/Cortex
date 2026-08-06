# Git Basics

Git is a distributed version control system created by Linus Torvalds in 2005 to manage development of the Linux kernel.

## Repository

A Git repository lives in the .git directory, which stores the complete history of the project. Cloning a repository copies everything, including all history, so every developer has a full backup.

## Staging area

The staging area, also called the index, is where changes wait before being committed. Files are added to it with git add. A commit is a snapshot of the staged changes, identified by a unique SHA-1 hash and carrying an author, a timestamp, and a message.

## Branches

A branch in Git is simply a movable pointer to a commit. Creating a branch is nearly instant and costs almost nothing. The default branch is commonly named main. HEAD points to the current branch, which is how Git knows where you are working.

## Merging and rebasing

Merging combines two branches by creating a merge commit, preserving the history of both sides. Rebasing moves commits onto a new base, rewriting history to make it linear. The golden rule of rebasing: never rebase branches that are shared with other people, because rewriting published history breaks everyone else's copies.

## Remotes

A remote is a version of the repository hosted elsewhere, for example on GitHub. git push uploads local commits to the remote, while git pull is a fetch followed by a merge.
