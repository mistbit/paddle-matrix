# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Paddle Matrix macOS App
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

# Get the project root directory
project_root = os.path.dirname(os.path.abspath(SPEC))

# Collect all hidden imports
hiddenimports = [
    # FastAPI and uvicorn
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'fastapi',
    'fastapi.middleware',
    'fastapi.middleware.cors',
    'starlette',
    'starlette.responses',
    'starlette.routing',
    'starlette.middleware',
    'starlette.middleware.cors',
    'starlette.staticfiles',

    # Pydantic
    'pydantic',
    'pydantic_settings',

    # OpenCV
    'cv2',

    # NumPy
    'numpy',
    'numpy.core',
    'numpy.core._multiarray_umath',

    # PaddleOCR and PaddlePaddle
    'paddle',
    'paddle.fluid',
    'paddle.dataset',
    'paddleocr',
    'paddleocr.ppocr',
    'paddleocr.ppocr.db_postprocess',
    'paddleocr.ppocr.utility',
    'paddleocr.ppocr.utils',
    'paddleocr.ppocr.utils.logging',
    'paddleocr.ppocr.utils.utility',
    'paddleocr.tools',
    'paddleocr.tools.infer',
    'paddleocr.ppstructure',
    'paddleocr.ppstructure.utility',

    # Additional dependencies
    'PIL',
    'PIL.Image',
    'scipy',
    'scipy.ndimage',
    'skimage',
    'imgaug',
    'pyclipper',
    'shapely',
    'lmdb',
    'tqdm',
    'visualdl',
    'python-dotenv',
    'aiofiles',

    # PyWebView for native window
    'webview',
    'webview.platforms',
    'webview.platforms.cocoa',
    'webview.platforms.cocoa guipython',
    'bottle',

    # PyObjC for macOS integration
    'objc',
    'Foundation',
    'Cocoa',
    'WebKit',
    'Quartz',
    'UniformTypeIdentifiers',
    'Security',

    # App modules
    'app',
    'app.main',
    'app.config',
    'app.api',
    'app.api.v1',
    'app.api.v1.subtitle',
    'app.services',
    'app.services.subtitle_service',
    'app.core',
    'app.core.video_processor',
    'app.core.ocr_engine',
    'app.core.subtitle_detector',
    'app.core.subtitle_merger',
    'app.core.srt_generator',
    'app.models',
    'app.models.domain',
    'app.models.schemas',
    'app.utils',
]

# Collect data files
datas = [
    # Static files
    (os.path.join(project_root, 'app', 'static'), 'app/static'),
    # Environment file if exists
]

# Include PaddleOCR/PaddleX models
paddlex_models_dir = os.path.expanduser('~/.paddlex/official_models')
if os.path.exists(paddlex_models_dir):
    datas.append((paddlex_models_dir, '.paddlex/official_models'))
    print(f"Including PaddleX models from: {paddlex_models_dir}")

# Try to collect additional data files from packages
try:
    # PaddleOCR data files (models, configs, etc.)
    paddleocr_datas = collect_data_files('paddleocr')
    datas.extend(paddleocr_datas)
except Exception:
    pass

try:
    # Paddle data files
    paddle_datas = collect_data_files('paddle')
    datas.extend(paddle_datas)
except Exception:
    pass

# Try to copy metadata for pydantic-settings
try:
    datas.extend(copy_metadata('pydantic-settings'))
except Exception:
    pass

try:
    datas.extend(copy_metadata('pydantic'))
except Exception:
    pass

try:
    datas.extend(copy_metadata('fastapi'))
except Exception:
    pass

# Binaries to exclude (OpenSSL libraries from OpenCV that conflict with Python's ssl module)
excluded_binaries = [
    'libcrypto.3.dylib',
    'libssl.3.dylib',
    'libcrypto.dylib',
    'libssl.dylib',
]

# Create Analysis
a = Analysis(
    ['app_launcher.py'],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[os.path.join(project_root, 'runtime_hook.py')],
    excludes=[
        'tkinter',
        'matplotlib',
        'notebook',
        'jupyter',
        'IPython',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# Filter out conflicting OpenSSL binaries from OpenCV
a.binaries = [x for x in a.binaries if not any(excl in x[0] for excl in excluded_binaries)]

# Also check datas for dylibs
filtered_datas = []
for data_item in a.datas:
    # data_item is a tuple (source, dest, type)
    if isinstance(data_item, tuple) and len(data_item) >= 2:
        src, dest = data_item[0], data_item[1]
        if not any(excl in src for excl in excluded_binaries):
            filtered_datas.append(data_item)
    else:
        filtered_datas.append(data_item)
a.datas = filtered_datas

# Create PYZ archive
pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=None,
)

# Create executable
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Paddle Matrix',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # GUI mode - no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# Collect all files for the app bundle
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    a.zipfiles,
    name='Paddle Matrix',
)

# Create macOS app bundle
app = BUNDLE(
    coll,
    name='Paddle Matrix.app',
    icon=None,  # You can add an .icns file path here
    bundle_identifier='com.paddle-matrix.app',
    version='1.0.0',
    info_plist={
        'CFBundleName': 'Paddle Matrix',
        'CFBundleDisplayName': 'Paddle Matrix',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleIdentifier': 'com.paddle-matrix.app',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.13.0',
        'NSPrincipalClass': 'NSApplication',
        'NSAppleScriptEnabled': False,
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'Video File',
                'CFBundleTypeRole': 'Viewer',
                'LSItemContentTypes': [
                    'public.mpeg-4',
                    'public.avi',
                    'public.quicktime-movie',
                    'org.matroska.mkv',
                    'org.webmproject.webm',
                ],
            }
        ],
    },
)