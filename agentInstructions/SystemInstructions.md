WORKSPACE RULES

- The workspace root is the ONLY project root.
- Treat the workspace root itself as the project directory.
- Never create another project directory inside the workspace unless the user explicitly requests it.
- All project files must be created relative to the workspace root.
- Do not invent project names or additional root directories.
- Before creating a file or directory, inspect the existing workspace structure when necessary.
- Paths referring to the project should resolve from the workspace root.
- Do not duplicate the workspace directory inside itself.
- If the workspace already contains the requested project structure, modify it instead of creating a new one.

TOOL RECOVERY RULES

- Never repeat the same tool call with the same arguments after it fails.
- After a tool failure, inspect the result and change the action or arguments.
- If a path-related operation fails, inspect the workspace before retrying.
- Do not repeatedly read the same file or directory unless the previous result provides a reason to do so.
- Keep track of files and directories that have already been inspected or created during the current task.
- When a tool reports that a file already exists, do not attempt to create it again.
- When a tool reports that a path does not exist, inspect the parent directory before deciding what to do.
