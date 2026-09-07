
from src.Tools.ToolResult import ToolResult
from typing import Any
from src.Tools.Tool import Tool
from pathlib import Path 


class Create(Tool):
    name='create'
    description = 'create a file'
    parameters = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "Path of the file to create."
        },
        "content": {
            "type": "string",
            "description": "Complete content to write into the new file."
        }
    },
    "required": ["file_path", "content"]
}

    def execute(self, file_path:str,content:str) -> Any:
        try:
            path = Path(file_path)
            if path.exists():
                return ToolResult(success=False,content=f"File already exists: {file_path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path,'w',encoding='utf-8') as f:
                    f.write(content)
                    return ToolResult(success=True,content=f"Created file: {file_path}")
        except Exception as e:
             return ToolResult(success=False,content=f'Cannot Write Files because of {e}')
