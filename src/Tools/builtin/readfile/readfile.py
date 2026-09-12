#src/Tools/readfile/readfile.py
from pathlib import Path
from src.Tools.Tool import Tool
from src.Tools.ToolResult import ToolResult
class ReadFile(Tool):
    name = 'Read'
    description = (
    "Read a file or list a directory.\n"
    "IMPORTANT:\n"
    "- If file_path points to a FILE, you may use start_line/end_line "
    "to read a specific line range.\n"
    "- If file_path points to a DIRECTORY, do NOT provide start_line "
    "or end_line. The tool will return the directory contents.\n"
    "- To inspect a directory, provide only file_path."
)
    parameters = {'type':'object',
                  'properties':{
                      'file_path':{
                        'type':'string',
                        'description':'path of the file or folder to read'},
                      'start_line':{
                        'type':'integer',
                        'description': 'First line to read. Optional.'},
                      'end_line':{
                        'type':'integer',
                        'description': 'Last line to read. Optional.'}
                        },'required': ['file_path'] }

        
    def execute(self,file_path:str,start_line:int=None,end_line:int=None):
                if not file_path:
                            return ToolResult(success=False,content='Path cannot be empty')
                                    
                try:

                    p = Path(file_path)
                    if p.is_file():
                        with open(p, 'r', encoding='utf-8') as f:
                            lines = f.readlines()

                        total_lines = len(lines)

                        if start_line is not None and start_line > total_lines:
                            return ToolResult(
                                success=False,
                                content=f'start_line ({start_line}) is beyond the end of the file ({total_lines} lines)'
                            )

                        if (
                            start_line is not None
                            and end_line is not None
                            and start_line > end_line
                        ):
                            return ToolResult(
                                success=False,
                                content=(
                                    f'start_line ({start_line}) must be '
                                    f'less than or equal to end_line ({end_line})'
                                )
                            )
                        if start_line is None:
                            start_idx = 0
                        else:
                            if start_line < 1:
                                
                                return ToolResult(success=False,content=f'start_line must be >= 1 (got {start_line})')
                            start_idx = start_line - 1


                        if end_line is None:
                            end_idx = total_lines
                        else:
                            if end_line < 1:
                                
                                return ToolResult(success=False,content=f'end_line must be >= 1 (got {end_line})')
                            end_idx = min(total_lines, end_line)  
                        content = ''.join(lines[start_idx:end_idx])
    
                        return ToolResult(success=True,content=content,metadata={
                                                        'total_lines': total_lines,
                                                        'start_line': start_idx + 1,
                                                        'end_line': end_idx,
                                                        'lines_returned': end_idx - start_idx
                                                    })
                    items = [] 
                    if p.is_dir():
                        for item in p.iterdir():
                            items.append(item)
                            
                        if items :
                            return ToolResult(success=True,content=f'Contents of {str(p.name)}:\n' + '\n'.join(str(item.name) for item in items),metadata={'total_files':len(items)})
                        return ToolResult(success=True,content='Directory is Empty.')
                     
                    return ToolResult(success=False,content='Nothing Found.')

                except UnicodeDecodeError:
                    
                    return ToolResult(success=False,content=f'Cannot read binary file: {file_path}')
                except Exception as e:
                    return ToolResult(success=False,content=f'Error {e}')