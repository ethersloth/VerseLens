# VerseLens

**Scripture Study, Notes & Strong’s** — an offline Bible reader for Android and Linux, built with Python and Qt (PySide6).

<img src="assets/verselens_icon.png" width="96" alt="VerseLens icon">

## Features

- Read by chapter, single verse, or verse range
- Notes (per translation or shared across all translations), bookmarks, and five highlight colours
- Side-by-side comparison of two translations, aligned by book, chapter and verse
- Strong’s-tagged editions (KJV-S, ASV-S) with tappable Strong’s numbers and an occurrence list
- Full-text search of the current translation
- Phone-first layout with light and dark themes (follows the system setting by default)
- Everything works offline; your notes stay on your device

## Included translations

All bundled texts are in the public domain.

| Code | Translation | Verses | Books |
|------|-------------|-------:|------:|
| KJV | Authorized King James Version | 31,102 | 66 |
| KJV-PCE | King James Version, Pure Cambridge Edition | 31,102 | 66 |
| KJV-S | King James Version with Strong’s numbers | 31,102 | 66 |
| ASV | American Standard Version | 31,101 | 66 |
| ASV-S | American Standard Version with Strong’s numbers | 31,086 | 66 |
| WEB | World English Bible | 31,098 | 66 |
| GNV | Geneva Bible | 31,102 | 66 |
| COV | Coverdale Bible | 31,102 | 66 |
| BISH | Bishops’ Bible | 31,097 | 66 |
| TYN | Tyndale Bible | 13,852 | 33 |

The KJV is public domain in most of the world; in the United Kingdom it is subject to perpetual Crown copyright.

## Install

Download from the [latest release](../../releases/latest):

- **Android:** `VerseLens-<version>.apk` — open it on your phone and allow installing from that source.
- **Linux (x86_64):** `VerseLens-<version>-x86_64.AppImage` — `chmod +x` it and run.

## Run from source

The scripture database is too large for the repository (GitHub limits files to 100 MB), so it is published with each release.

```bash
git clone https://github.com/ethersloth/VerseLens.git
cd VerseLens
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# download bible.db from the latest release into data/
mkdir -p data
gh release download --pattern bible.db --dir data   # or download it from the Releases page
python main.py
```

User notes, bookmarks, highlights and settings are stored separately in the operating system’s application-data directory (`annotations.db`), so replacing `data/bible.db` never touches them.

## Build for Android

The Android build uses [buildozer](https://buildozer.readthedocs.io/) with PySide6’s Qt bootstrap for python-for-android.

1. Build the PySide6 and shiboken6 Android (aarch64, CPython 3.11) wheels from [pyside-setup](https://code.qt.io/cgit/pyside/pyside-setup.git/) and point `wheel_pyside` / `wheel_shiboken` in `pysidedeploy.spec` at them.
2. Run `pyside6-android-deploy` once to download the Android SDK/NDK and generate `deployment/` (Qt jars and recipes).
3. Update the machine-specific paths in `buildozer.spec` and `pysidedeploy.spec` (`android.ndk_path`, `android.sdk_path`, `p4a.local_recipes`, `android.add_jars`, `icon.filename`, `bin_dir`).
4. From a Python 3.11 environment with buildozer installed:

   ```bash
   python -m buildozer android debug
   ```

Run buildozer directly rather than through `pyside6-android-deploy` after the first run: the deploy tool regenerates `buildozer.spec` and drops the `source.exclude_*` lines that keep build folders out of the APK.

## Adding data

### Another translation

```bash
python tools/import_translation.py /path/to/version.txt --code CODE --name "Version Name" --rights "Rights statement"
```

For a copyrighted text you are licensed to use privately, add `--local-only`; it is marked non-redistributable. Do not publish builds that contain such texts.

### A Strong’s lexicon

The bundled database has Strong’s references but no dictionary definitions yet. You can import:

- a CSV/TSV with columns `strong_number`, `language`, `lemma`, `transliteration`, `pronunciation`, `definition`:

  ```bash
  python tools/import_lexicon.py strongs_lexicon.tsv --source "Lexicon source"
  ```

- the Open Scriptures [strongs](https://github.com/openscriptures/strongs) and [HebrewLexicon](https://github.com/openscriptures/HebrewLexicon) projects:

  ```bash
  python tools/import_openscriptures_lexicons.py \
    --strongs-repo ../strongs \
    --hebrew-lexicon-repo ../HebrewLexicon
  ```

  Keep their attribution in your documentation if you redistribute data derived from them.

## License

The VerseLens code is released under the [MIT License](LICENSE). The bundled scripture texts are in the public domain.
