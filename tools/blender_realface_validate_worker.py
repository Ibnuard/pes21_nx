"""Keep Blender loaded while independently validating successive face profiles."""
import json
from pathlib import Path
import sys
import traceback

PREFIX = 'PESNX_VALIDATION_RESULT '


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from validate_realface_cooked import validate
    # validate_part clears Blender's scene before each mesh; no scene or rig
    # state from one player is reused by another player.
    for line in sys.stdin:
        request = json.loads(line)
        result = dict(token=request['token'], ok=False)
        try:
            validate(json.loads(Path(request['profile']).read_text(encoding='utf-8')))
            result['ok'] = True
        except Exception as error:
            traceback.print_exc()
            result['reason'] = str(error)
        print(PREFIX + json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
