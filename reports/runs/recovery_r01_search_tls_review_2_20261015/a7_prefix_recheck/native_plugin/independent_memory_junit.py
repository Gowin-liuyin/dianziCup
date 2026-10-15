import base64, builtins, io, os, sys, json
original = builtins.open
buffer = None
class NativeJUnitMemory(io.StringIO):
    def close(self):
        pass
def guarded_open(file, mode="r", *args, **kwargs):
    global buffer
    if isinstance(file, (str, os.PathLike)) and os.fspath(file).endswith("review-native.xml") and "w" in mode:
        buffer = NativeJUnitMemory()
        return buffer
    return original(file, mode, *args, **kwargs)
def pytest_configure(config):
    builtins.open = guarded_open
def pytest_unconfigure(config):
    builtins.open = original
    if buffer is not None:
        print("REVIEW_MEMORY_JUNIT=" + base64.b64encode(buffer.getvalue().encode()).decode())
    observed = getattr(sys.modules.get("test_independent_failure"), "OBSERVED", [])
    print("REVIEW_MEMORY_VALUES=" + base64.b64encode(json.dumps(observed).encode()).decode())
