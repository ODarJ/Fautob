# ObetyPl — နေ့စဉ်ရှုခင်းဗီဒီယို (Facebook မတင်သေးပါ)

## ဒီ code က ဘာလုပ်မလဲ
- Gemini က 60 စက္ကန့် landscape video အတွက် scene idea နဲ့ သီချင်း ၅ ပုဒ်ထဲက တစ်ပုဒ်ရွေးမယ်။
- Pexels က landscape video clips တွေကို ရှာပြီး download လုပ်မယ်။
- FFmpeg နဲ့ 1920×1080 MP4၊ ObetyPl watermark၊ ရွေးထားတဲ့ music တို့ကို ပေါင်းမယ်။
- GitHub Actions မှာ MP4 ကို Artifact အဖြစ် သိမ်းမယ်။
- **Facebook ကို မတင်ပါ။**

## GitHub ထဲ ထည့်ရမယ့်ဖိုင်များ
ဒီ ZIP ကိုဖြည်ပြီး အောက်ပါအတိုင်း Repository `ODarJ/Fautob` ရဲ့ `main` branch ထဲတင်ပါ။
- `.github/workflows/obetypl.yml`
- `make_video.py`
- `requirements.txt`
- `README_SETUP_BURMESE.md`

သီချင်း MP3 ၅ ပုဒ်ကို `Assets/` ထဲမှာ ဆက်ထားပါ။ ဖိုင်နာမည်တွေကို workflow နဲ့ script ထဲက နာမည်တွေနဲ့ တူအောင်ထားပါ။

## API keys ထည့်နည်း
1. https://github.com/ODarJ/Fautob/settings/secrets/actions ဖွင့်ပါ.
2. `New repository secret` နှိပ်ပါ.
3. Name = `GEMINI_API_KEY`, Secret = Google AI Studio မှရတဲ့ API key. Save.
4. `New repository secret` ထပ်နှိပ်ပါ.
5. Name = `PEXELS_API_KEY`, Secret = Pexels API key. Save.
6. API key ကို ChatGPT သို့မဟုတ် public file ထဲ မထည့်ပါနဲ့။

Gemini API key: https://aistudio.google.com/apikey
Pexels API: https://www.pexels.com/api/

## စမ်းသပ် run လုပ်နည်း
1. Repository > Actions ကိုဖွင့်ပါ။
2. `ObetyPl Daily Scenic Video` ကိုရွေးပါ။
3. `Run workflow` နှိပ်ပါ။ Scenery idea မပေးချင်ရင် blank ထားနိုင်ပါတယ်။
4. Run ပြီးဆုံးတဲ့အခါ အောက်ဆုံးမှာ `obetypl-video-...` Artifact ZIP ကို download လုပ်ပါ။
5. ZIP ကိုဖြည်ပြီး MP4 ကို စစ်ဆေးပါ။

Schedule သည် နေ့စဉ် UTC 01:00 ဖြစ်ပြီး ထိုင်းစံတော်ချိန် 08:00 ဖြစ်ပါတယ်။ GitHub scheduled workflow များသည် တစ်ခါတစ်ရံ နောက်ကျနိုင်ပါတယ်။

## အရေးကြီး
- Gemini က သီချင်းကို နားထောင်ပြီး မရွေးပါ။ သီချင်းနာမည်/အဆိုရှင်အချက်အလက်အပေါ်သာ ရွေးပါတယ်။
- Pexels clip များကို စနစ်က query နဲ့ ရွေးထားတာဖြစ်ပြီး Gemini က video thumbnail တစ်ခုချင်းကို မစစ်ဆေးသေးပါ။
- Pexels API usage limits နှင့် MP3/stock video လိုင်စင်ကို စစ်ဆေးပါ။
- ဤစနစ်သည် Facebook Page ကို မတင်ပါ။
- Output ကို အရင်စစ်ပါ။ Clip အချို့ မရနိုင်ခြင်း၊ API quota ကန့်သတ်ချက်၊ key မှားခြင်းတို့ကြောင့် run မအောင်မြင်နိုင်ပါ။
