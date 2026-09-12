"""Native packaging diagnostics, enabled only by the synthetic smoke-test flag."""
import sys

if '--smoke-test' in sys.argv:
    def trace_missing_file(frame, event, arg):
        if event == 'exception' and isinstance(arg[1], FileNotFoundError):
            if '/docx/' in frame.f_code.co_filename or frame.f_code.co_filename.endswith('formats.py'):
                print('Packaging missing file:', str(arg[1]), file=sys.stderr, flush=True)
        return trace_missing_file
    sys.settrace(trace_missing_file)
