name: ObetyPl Daily Scenic Video

on:
  workflow_dispatch:
    inputs:
      scenery:
        description: "Optional scenery idea (leave blank for AI to choose)"
        required: false
        type: string
        default: ""

  schedule:
    # Every day at 01:00 UTC = 08:00 Thailand time
    - cron: "0 1 * * *"

permissions:
  contents: read

concurrency:
  group: obetypl-video
  cancel-in-progress: false

jobs:
  make-video:
    runs-on: ubuntu-latest
    timeout-minutes: 45

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Install Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install FFmpeg
        run: |
          sudo apt-get update
          sudo apt-get install -y ffmpeg

      - name: Install Python dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Generate 60-second ObetyPl video
        env:
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
          PEXELS_API_KEY: ${{ secrets.PEXELS_API_KEY }}
          GROQ_MODEL: openai/gpt-oss-20b
          INPUT_SCENERY: ${{ inputs.scenery }}
        run: python make_video.py

      - name: Upload MP4 and planning report
        uses: actions/upload-artifact@v4
        with:
          name: obetypl-video-${{ github.run_number }}
          path: |
            output/ObetyPl_*.mp4
            output/plan.json
          if-no-files-found: error
          retention-days: 14