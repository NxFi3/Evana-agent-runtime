#!/usr/bin/env python3
import os, sys, types, time
from datetime import datetime
# Create 'src' package pointing to repository's src dir
src_pkg = types.ModuleType('src')
src_pkg.__path__ = [os.path.join(os.getcwd(), 'src')]
sys.modules['src'] = src_pkg

# Dummy logger
utils_logger_mod = types.ModuleType('src.Utils.logger')
def get_logger(name):
    class DummyLogger:
        def __init__(self, name): self.name=name
        def info(self,msg): pass
        def warning(self,msg): pass
        def error(self,msg): pass
        def debug(self,msg): pass
    return DummyLogger(name)
utils_logger_mod.get_logger = get_logger
sys.modules['src.Utils.logger'] = utils_logger_mod

# Dummy Retrieval
retrieval_mod = types.ModuleType('src.Memory.Retrieval')
class DummyRetrieval:
    def get_nearest_memory(self, query): return None
retrieval_mod.Retrieval = DummyRetrieval
sys.modules['src.Memory.Retrieval'] = retrieval_mod

# Dummy LLM provider
llm_provider_mod = types.ModuleType('src.Engine.llmManagment.LlmProvider')
class DummyLlmProvider:
    def generate(self, prompt):
        # Return an empty JSON list
        return "[]"
llm_provider_mod.LlmProvider = DummyLlmProvider
sys.modules['src.Engine.llmManagment.LlmProvider'] = llm_provider_mod

# Dummy DatabaseManager
db_mod = types.ModuleType('src.Memory.DatabaseManager')
class DummyDBManager: pass
db_mod.DBManager = DummyDBManager
sys.modules['src.Memory.DatabaseManager'] = db_mod

# Dummy MemoryEvent
mem_event_mod = types.ModuleType('src.Memory.MemoryEvent')
class MemoryEvent:
    def __init__(self,id,event_type,content,source,step,timestamp,metadata):
        self.id=id; self.event_type=event_type; self.content=content
        self.source=source; self.step=step; self.timestamp=timestamp
        self.metadata=metadata
mem_event_mod.MemoryEvent = MemoryEvent
sys.modules['src.Memory.MemoryEvent'] = mem_event_mod

# Dummy MemoryParser
mem_parser_mod = types.ModuleType('src.Memory.MemoryParser')
class DummyParser:
    def parse(self, response):
        # Simply return empty list to mimic no decisions
        try:
            import json
            return json.loads(response)
        except Exception:
            return []
mem_parser_mod.MemoryParser = DummyParser
sys.modules['src.Memory.MemoryParser'] = mem_parser_mod

# Dummy MemoryPrompt (build_decision_prompt) simply returns context string
mem_prompt_mod = types.ModuleType('src.Memory.MemoryPrompt')
def build_decision_prompt(context):
    return context  # echo back, not used by dummy LLM
mem_prompt_mod.build_decision_prompt = build_decision_prompt
sys.modules['src.Memory.MemoryPrompt'] = mem_prompt_mod

# Import the class under test from its real file path
from src.Memory.MemoryConsolidator import MemoryConsolidator

# Instantiate consolidator with dummy args (LLM provider not needed for current logic)
consolidator = MemoryConsolidator(DummyLlmProvider(), DummyDBManager(), DummyRetrieval(), DummyParser())

N_EVENTS=20000
events_batch=[MemoryEvent(
    id=i,
    event_type='user_input',
    content=f'Sample event number {i}',
    source='user',
    step=1,
    timestamp=datetime.utcnow(),
    metadata={}
) for i in range(N_EVENTS)]

start=time.perf_counter()
results=consolidator.process(events_batch)
end=time.perf_counter()
elapsed_ms=(end-start)*1000
throughput_events_per_sec=N_EVENTS/(end-start)
print('\n=== Benchmark Summary ===')
print(f'Processed {N_EVENTS} events in {elapsed_ms:.1f} ms (≈{throughput_events_per_sec:.1f} events/sec)')
print('\nFirst 5 results:')
for r in results[:5]:
    print(r)
