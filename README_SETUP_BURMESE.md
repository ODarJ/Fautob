# ObetyPl — နေ့စဉ်ရှုခင်းဗီဒီယို (Facebook မတင်သေးပါ)

## ဒီ code က ဘာလုပ်မလဲ
- **Groq** AI က 60 စက္ကန့် **vertical (9:16)** nature video အတွက် scene plan နဲ့ caption ရေးတယ်။
- **Pexels** က real video footage တွေကို ရှာပြီး download လုပ်တယ် (photo မသုံးဘူး)။
- **FreeSound** က သင့်တော်တဲ့ background music ကို ရှာတယ် (CC0 / CC-BY license ပဲ လက်ခံ)။
- FreeSound မရရင် `Assets/` ထဲက သီချင်း ၅ ပုဒ်ထဲက တစ်ပုဒ်ကို fallback အဖြစ် သုံးတယ်။
- **FFmpeg** နဲ့ 1080×1920 MP4၊ ObetyPl watermark၊ ရွေးထားတဲ့ music တို့ကို ပေါင်းတယ်။
- GitHub Actions မှာ MP4 နဲ့ report တွေကို Artifact အဖြစ် သိမ်းတယ်။
- Content history ကို `data/content_history.json` မှာ မှတ်ပြီး နောက်နေ့တွေမှာ ထပ်မတူအောင် ကာကွယ်တယ်။
- **Facebook ကို မတင်ပါ။** ကိုယ်တိုင် review လုပ်ပြီးမှ တင်ရမယ်။

## GitHub ထဲ ထည့်ရမယ့်ဖိုင်များ
ZIP ကိုဖြည်ပြီး Repository `ODarJ/Fautob` ရဲ့ `main` branch ထဲ တင်ပါ။
- `.github/workflows/obetypl.yml`
- `make_video.py`
- `requirements.txt`
- `src/` (folder တစ်ခုလုံး)
- `data/` (folder တစ်ခုလုံး)
- `tests/` (optional)
- `README.md` နှင့် `README_SETUP_BURMESE.md`
- `Assets/` ထဲက သီချင်း MP3 ၅ ပုဒ် (မဖျက်ရ)

## သီချင်းဖိုင် ၅ ပုဒ် (Assets/)
အောက်ပါ ဖိုင်နာမည်တွေ အတိအကျ ရှိရမယ် (em-dash `—` သုံးထားတယ်)။

1. `01 — Silent Descent.mp3`
2. `02 — Beautiful Dream.mp3`
3. `03 — Classical vibes 2.mp3`
4. `04 — Emotional.mp3`
5. `05 — Dramatic Piano Background.mp3`

**အရေးကြီး:** ဒီဖိုင်တွေရဲ့ license ကို system က အလိုအလျောက် မစစ်နိုင်ပါ။ Commercial Facebook သုံးမယ်ဆိုရင် ကိုယ်တိုင် စစ်ဆေးပါ။

## API keys (GitHub Secrets) ထည့်နည်း
1. https://github.com/ODarJ/Fautob/settings/secrets/actions ဖွင့်ပါ။
2. `New repository secret` နှိပ်ပါ။

| Secret နာမည် | လိုအပ်မှု | ရှင်းလင်းချက် |
|--------------|----------|----------------|
| `GROQ_API_KEY` | မဖြစ်မနေ | Creative Director (AI planning) |
| `PEXELS_API_KEY` | မဖြစ်မနေ | Video footage |
| `FREESOUND_API_KEY` | သုံးချင်ရင် | FreeSound music search & preview |

3. API key ကို public file သို့မဟုတ် chat ထဲ မထည့်ပါနဲ့။

### FreeSound အကြောင်း
- Search နှင့် preview download အတွက် `FREESOUND_API_KEY` (Token) လုံလောက်ပါတယ်။
- Original high-quality file download အတွက် OAuth2 လိုအပ်ပြီး **ဒီ project မှာ မထည့်ရသေးပါ**။
- Preview ပဲ သုံးပါတယ်။
- CC0 နှင့် plain CC-BY license ရှိတာကိုသာ လက်ခံပါတယ်။ NC / ND / SA ကို ငြင်းပါတယ်။
- Key မရှိရင် သို့မဟုတ် သင့်တော်တဲ့ sound မတွေ့ရင် local Assets/ သီချင်းကို အလိုအလျောက် သုံးပါတယ်။

## စမ်းသပ် run လုပ်နည်း
1. Repository > **Actions** ကိုဖွင့်ပါ။
2. **ObetyPl Daily Scenic Video** ကိုရွေးပါ။
3. **Run workflow** နှိပ်ပါ။ Scenery idea မပေးချင်ရင် blank ထားနိုင်ပါတယ်။
4. Run ပြီးဆုံးတဲ့အခါ အောက်ဆုံးမှာ `obetypl-video-...` Artifact ZIP ကို download လုပ်ပါ။
5. ZIP ကိုဖြည်ပြီး စစ်ဆေးပါ။
   - `ObetyPl_*.mp4` — ဗီဒီယို
   - `caption.txt` — Facebook မှာ ကူးထည့်မယ့် စာသား
   - `plan.json` — AI ရဲ့ scene plan
   - `music_report.json` — သီချင်း ဘယ်ကလာလဲ၊ license ဘာလဲ
   - `quality_report.json` — အလိုအလျောက် စစ်ဆေးချက်
   - `attribution.txt` — credit ပေးရမယ့် အချက်

Schedule သည် နေ့စဉ် **UTC 01:00** (ထိုင်းစံတော်ချိန် 08:00) ဖြစ်ပါတယ်။ GitHub scheduled workflow များသည် တစ်ခါတစ်ရံ နောက်ကျနိုင်ပါတယ်။

## Content History
- `data/content_history.json` မှာ ယခင် video တွေ မှတ်ထားတယ်။
- Workflow အောင်မြင်ရင် history ကို git commit လုပ်ပြီး repo ထဲ ပြန်သိမ်းတယ်။
- နောက်နေ့ AI က အရင်က သုံးခဲ့တဲ့ concept ကို မထပ်အောင် ရှောင်တယ်။

## Music License သတိပေးချက်
- FreeSound က ရတဲ့ track မှာ license နဲ့ attribution info ကို `music_report.json` နှင့် `attribution.txt` မှာ ရေးထားတယ်။
- Local Assets/ track တွေအတွက် license ကို **unknown** လို့ မှတ်ထားတယ်။ Commercial သုံးမယ်ဆိုရင် ကိုယ်တိုင် စစ်ပါ။
- System က "copyright-free" လို့ မပြောပါ။

## အရေးကြီး
- ဤစနစ်သည် Facebook Page ကို **မတင်ပါ**။
- Output ကို အရင်စစ်ပါ။ API key မှားခြင်း၊ quota ကုန်ခြင်း၊ clip မရခြင်းတို့ကြောင့် run မအောင်မြင်နိုင်ပါ။
- FreeSound original download အတွက် OAuth2 ကို မထည့်ရသေးပါ။
- Local music license ကို အလိုအလျောက် မအတည်ပြုပါ။

## Test များ
```bash
pip install -r requirements.txt
pytest tests/ -v
```
