# Git Workflow

Follow this workflow when contributing to the project:

## 0. Clone the Repository (First Time Only)

If you haven't already, clone the repo to your local machine:

```bash
git clone https://github.com/AndrewKelton/large-project
cd large-project
```

## 1. Get the Most Recent Changes

Before starting any work, pull the latest changes from the `dev` branch:

```bash
git checkout dev
git pull origin dev
```

## 2. Create a Feature Branch

Create a new branch for your work. Use the naming convention based on the Jira ticket number for the feature you're working on:

```bash
git checkout -b LEE-<ticket-num>/<feature-name>
```

Replace `<ticket-num>` with the Jira ticket number and `<feature-name>` with a short, descriptive name for the feature (e.g., `LEE-42/user-authentication`, `LEE-7/database-optimization`, `LEE-15/map-clustering`).

> ⚠️ **Branch Naming Convention:** Always use `-` (hyphens) to separate words in branch names. **Never use `_` (underscores)** — this is bad practice and inconsistent with Git conventions (e.g., use `LEE-42/user-auth` not `LEE-42/user_auth`).

## 3. Commit Changes Regularly

> 💡 **Before committing, always verify you're on the correct branch!** Run the following in your terminal to confirm:
> ```bash
> git branch
> ```
> Your current branch will be highlighted with a `*`. If you're not on the right branch, switch before committing.

As you work, commit your changes regularly with clear, descriptive commit messages:

```bash
git add .
git commit -m "Description of changes made"
```

## 4. Push Your Changes

Push your branch when you reach a good point in your work. A "good point" means:
- Your code compiles/runs without errors
- You've completed a logical unit of work (a complete feature or significant portion)
- Your changes are tested and working as intended
- You want to back up your work or share progress with the team

```bash
git push origin <your-branch-name>
```

or
```bash
git push
```

## 5. Create a Pull Request

The first time you push, you'll see a pull request link in the terminal. **CMD+click on this link** to open the pull request in your browser.

**⚠️ Important:** Make sure you set the base branch to `dev`, **NOT** `main`. This ensures your changes are reviewed and tested on the development branch before being merged to production.

## 6. Merge Into Dev

Once your feature is complete and reviewed, merge it into the `dev` branch:

```bash
git checkout dev
git merge <your-branch-name>
```

Alternatively, you can merge through the pull request interface on GitHub.

# Testing Features in Staging

Our `staging` branch is used for live deployment testing. Here's how to test your feature branches before merging to `dev`:

## Testing Your Feature Branch in Staging

1. **Push your feature branch to the staging branch:**
   ```bash
   git checkout staging
   git merge <your-feature-branch>
   git push origin staging
   ```

2. **Test your changes on the live server:**
   - Visit `<http://leandrovivares.com/>` to see your changes deployed
   - The deployment happens automatically via GitHub Actions

3. **Once testing is complete, reset staging:**
   ```bash
   git checkout staging
   git reset --hard origin/dev
   git push origin staging --force
   ```

## ⚠️ CRITICAL STAGING RULES

**NEVER do the following with the staging branch:**
- ❌ NEVER merge `staging` into `dev`
- ❌ NEVER merge `staging` into `main`
- ❌ NEVER open a Pull Request FROM `staging`
- ❌ NEVER keep experimental code in `staging` permanently

**Why?** The `staging` branch is a temporary testing environment. It should mirror `dev` when not actively testing features.

## Staging Workflow Best Practices

1. `staging` should normally mirror `dev`
2. Only merge feature branches into `staging` temporarily for testing
3. Always reset `staging` back to `dev` after testing
4. > ⚠️ **Only merge tested features from YOUR feature branch into `dev`, not from `staging`**

# Using VS Code Git Control

VS Code has built-in git tools that make version control easier without using the terminal:

## Accessing Git Control

1. Click the **Source Control** icon in the left sidebar (it looks like a branch)
2. Or use the keyboard shortcut: `Ctrl+Shift+G` (Windows/Linux) or `Cmd+Shift+G` (Mac)

## Basic Operations

**Staging Changes:**
- View all modified files in the "Changes" section
- Click the `+` icon next to a file to stage it for commit
- Or click the `+` icon in the "Changes" header to stage all files

**Committing Changes:**
- Enter a commit message in the text field at the top of the Source Control panel
- Click the checkmark icon to commit, or press `Ctrl+Enter` (Windows/Linux) or `Cmd+Enter` (Mac)

**Viewing History:**
- Right-click a file in the Source Control panel and select "Open Timeline" to see commit history
- Or use the `Gitlens` extension for more advanced history viewing

## Creating a Branch in VS Code

1. Click the branch name at the bottom left
2. Select "Create New Branch..."
3. Enter your branch name following the convention: `front-end/<feature>` or `api/<feature>`
4. Select `dev` as the base branch when prompted

---
