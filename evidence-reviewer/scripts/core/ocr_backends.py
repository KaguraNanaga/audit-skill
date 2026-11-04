"""Optional, local-only OCR adapters. No model acquisition or automatic fallback."""
import csv
import importlib.metadata
import importlib.util
import io
import json
import re
from pathlib import Path
import shutil
import sys

if __package__:
    from .converters import run_tool
    from .readers import digest
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from core.converters import run_tool
    from core.readers import digest


def describe(engine):
    if engine == 'tesseract':
        executable = shutil.which('tesseract')
        if not executable:
            raise FileNotFoundError('tesseract executable unavailable')
        version, _ = run_tool([executable, '--version'], timeout=10)
        languages, _ = run_tool([executable, '--list-langs'], timeout=10)
        if not {'chi_sim', 'eng'} <= set(languages.splitlines()):
            raise FileNotFoundError('tesseract requires both chi_sim and eng language data')
        match = re.search(r'in "([^"]+)"', languages)
        models = {}
        if match:
            for language in ('chi_sim', 'eng'):
                model = Path(match.group(1)) / (language + '.traineddata')
                if model.is_file(): models[language] = dict(path=str(model), sha256=digest(model))
        return dict(engine=engine, version=version.splitlines()[0], executable=executable, models=models,
                    executable_sha256=digest(Path(executable)), parameters={'languages': 'chi_sim+eng', 'psm': 3, 'oem': 1, 'output': 'tsv'})
    if engine != 'rapidocr':
        raise ValueError('Unknown OCR engine')
    spec = importlib.util.find_spec('rapidocr_onnxruntime')
    if not spec or not spec.origin:
        raise FileNotFoundError('Optional rapidocr-onnxruntime package unavailable')
    folder = Path(spec.origin).parent / 'models'
    models = {}
    for kind in ('det', 'cls', 'rec'):
        candidates = sorted(folder.glob('*' + kind + '*.onnx'))
        if len(candidates) != 1:
            raise FileNotFoundError('Exactly one bundled local RapidOCR ' + kind + ' model required; models are never downloaded')
        models[kind] = dict(path=str(candidates[0]), sha256=digest(candidates[0]))
    configuration = Path(spec.origin).parent / 'config.yaml'
    return dict(engine=engine, version=importlib.metadata.version('rapidocr-onnxruntime'),
                runtime_version=importlib.metadata.version('onnxruntime'), models=models,
                parameters={'configuration': configuration.read_text(encoding='utf-8'), 'configuration_sha256': digest(configuration),
                            'intra_op_num_threads': 1, 'inter_op_num_threads': 1, 'network': 'disabled', 'telemetry': 'disabled'})


def recognize(image, output, metadata, timeout):
    image, output = Path(image).resolve(), Path(output).resolve()
    if not image.is_file():
        raise FileNotFoundError('Registered page image missing')
    if metadata['engine'] == 'tesseract':
        text, _ = run_tool([metadata['executable'], str(image), 'stdout', '-l', 'chi_sim+eng', '--psm', '3', '--oem', '1', 'tsv'], timeout)
        blocks = []
        for row in csv.DictReader(io.StringIO(text), delimiter='\t'):
            if row.get('level') != '5' or not row.get('text', '').strip():
                continue
            x, y, w, h = (int(row[k]) for k in ('left', 'top', 'width', 'height'))
            confidence = float(row['conf'])
            blocks.append(dict(text=row['text'], confidence=confidence / 100,
                               bbox=[[x,y],[x+w,y],[x+w,y+h],[x,y+h]], frame=int(row['page_num'])))
        return blocks
    models = metadata['models']
    # Isolated worker gives the Python backend the same bounded process lifetime as a CLI.
    run_tool([sys.executable, '-B', str(Path(__file__).resolve()), str(image), str(output),
              *[models[k]['path'] for k in ('det','cls','rec')]], timeout)
    return json.loads(output.read_text(encoding='utf-8'))


def worker():
    def offline(event, args):
        if event in {'socket.connect', 'socket.connect_ex', 'socket.getaddrinfo', 'socket.bind'}:
            raise RuntimeError('Network access disabled in OCR worker')
    sys.addaudithook(offline)
    import onnxruntime
    onnxruntime.disable_telemetry_events()
    from rapidocr_onnxruntime import RapidOCR
    image, output, det, cls, rec = sys.argv[1:]
    engine = RapidOCR(det_model_path=det, cls_model_path=cls, rec_model_path=rec,
                      intra_op_num_threads=1, inter_op_num_threads=1)
    result, _ = engine(str(Path(image).resolve()))
    blocks = [dict(bbox=box, text=text, confidence=float(score), frame=1) for box,text,score in (result or [])]
    Path(output).write_text(json.dumps(blocks, ensure_ascii=False, allow_nan=False), encoding='utf-8')


if __name__ == '__main__':
    # Running the file directly does not import the package's relative imports above.
    worker()
