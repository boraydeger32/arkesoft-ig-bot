#!/bin/bash
# ============================================================
#  ARKESOFT Instagram botu — TEK SEFERLİK KURULUM (Mac)
#  Çalıştırın:  bash setup.sh
#  Her adımda ne yapacağınızı söyler; sadece istenen şeyi yapıştırın.
#  Kurulum bitince bot tamamen bulutta (GitHub) çalışır, Mac'e ihtiyaç kalmaz.
# ============================================================
set -e
cd "$(dirname "$0")"
ROOT="$(pwd)"
ENV="$ROOT/.env"
touch "$ENV"

say_() { printf "\n\033[1;36m%s\033[0m\n" "$*"; }
ask()  { printf "\033[1;33m%s\033[0m" "$1"; read -r REPLY; echo "$REPLY"; }
setenv() { # setenv KEY VALUE → .env'e yazar (varsa değiştirir)
  grep -v "^$1=" "$ENV" > "$ENV.tmp" 2>/dev/null || true; mv "$ENV.tmp" "$ENV"; echo "$1=$2" >> "$ENV"; }
getenv() { grep "^$1=" "$ENV" 2>/dev/null | head -1 | cut -d= -f2-; }

say_ "1/8  Araçlar kuruluyor (Homebrew, git, node, python, gh)…"
if ! command -v brew >/dev/null; then
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"
fi
brew list git >/dev/null 2>&1 || brew install git
brew list node >/dev/null 2>&1 || brew install node
brew list python >/dev/null 2>&1 || brew install python
brew list gh >/dev/null 2>&1 || brew install gh
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q requests
command -v claude >/dev/null || npm install -g @anthropic-ai/claude-code

say_ "2/8  Claude Code — Max aboneliğinizle bulut anahtarı"
if [ -z "$(getenv CLAUDE_CODE_OAUTH_TOKEN)" ]; then
  echo "Şimdi 'claude setup-token' çalışacak. Tarayıcı açılırsa Max hesabınızla giriş yapıp onaylayın."
  echo "Komut sonunda 'sk-ant-oat...' ile başlayan uzun bir anahtar gösterecek; onu kopyalayın."
  ask "Hazırsanız Enter'a basın…" >/dev/null
  claude setup-token || true
  T=$(ask "Gösterilen anahtarı buraya yapıştırın: ")
  setenv CLAUDE_CODE_OAUTH_TOKEN "$T"
else echo "✔ zaten var"; fi

say_ "3/8  GitHub"
gh auth status >/dev/null 2>&1 || gh auth login
OWNER=$(gh api user -q .login)
REPO="arkesoft-ig-bot"
if [ ! -d .git ]; then git init -b main >/dev/null; fi
git add -A >/dev/null; git -c user.name="setup" -c user.email="setup@local" commit -qm "ilk kurulum" >/dev/null 2>&1 || true
if ! gh repo view "$OWNER/$REPO" >/dev/null 2>&1; then
  gh repo create "$REPO" --public --source=. --push >/dev/null
else
  git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$OWNER/$REPO.git"
  git push -u origin main >/dev/null 2>&1 || true
fi
# GitHub Pages: "GitHub Actions" kaynağı
gh api -X POST "repos/$OWNER/$REPO/pages" -f build_type=workflow >/dev/null 2>&1 || gh api -X PUT "repos/$OWNER/$REPO/pages" -f build_type=workflow >/dev/null 2>&1 || true
echo "✔ Depo: https://github.com/$OWNER/$REPO"

say_ "4/8  Telegram bildirimleri"
if [ -z "$(getenv TELEGRAM_CHAT_ID)" ]; then
  echo "Telefonunuzda Telegram'ı açın → @BotFather'a yazın:  /newbot"
  echo "Bir ad (örn. Arkesoft Bot) ve kullanıcı adı (örn. arkesoft_ig_bot) verin. Size bir TOKEN verecek."
  echo "Sonra yeni botunuzu açıp 'merhaba' yazın (bu önemli)."
  T=$(ask "BotFather'ın verdiği TOKEN'ı yapıştırın: ")
  until python3 scripts/telegram_setup.py "$T"; do ask "Bota 'merhaba' yazdıktan sonra Enter'a basın…" >/dev/null; done
else echo "✔ zaten bağlı"; fi

say_ "5/8  Instagram (Meta) anahtarları"
if [ -z "$(getenv IG_USER_ID)" ]; then
  cat <<'EOT'
Tarayıcıda şu adımları yapın (sayfalar şimdi açılacak):
  a) developers.facebook.com → My Apps → Create App → "Other" → "Business" → ad: Arkesoft IG Bot
  b) Uygulamada: Add product → Instagram → "Instagram API with Facebook Login" → Set up
  c) App settings → Basic → App ID ve App Secret (Show) → not alın
  d) Tools → Graph API Explorer → sağda uygulamanızı seçin → Permissions'a ekleyin:
     instagram_basic, instagram_content_publish, pages_show_list, pages_read_engagement, business_management
     → Generate Access Token → Instagram hesabınızı ve bağlı sayfayı seçin → token'ı kopyalayın
EOT
  open "https://developers.facebook.com/apps/" 2>/dev/null || true
  APP_ID=$(ask "App ID: ")
  APP_SECRET=$(ask "App Secret: ")
  open "https://developers.facebook.com/tools/explorer/" 2>/dev/null || true
  TOKEN=$(ask "Graph API Explorer token'ı: ")
  python3 scripts/setup_token.py "$APP_ID" "$APP_SECRET" "$TOKEN"
else echo "✔ zaten var"; fi

say_ "6/8  Seslendirme (isteğe bağlı — boş bırakırsanız anahtarsız Edge sesi kullanılır)"
if [ -z "$(getenv AZURE_SPEECH_KEY)" ] && [ -z "$(getenv ELEVEN_API_KEY)" ] && [ -z "$(getenv GOOGLE_TTS_API_KEY)" ]; then
  K=$(ask "Azure Speech KEY (yoksa Enter): ")
  if [ -n "$K" ]; then R=$(ask "Azure region (örn. westeurope): "); setenv AZURE_SPEECH_KEY "$K"; setenv AZURE_SPEECH_REGION "$R"; fi
  K=$(ask "ElevenLabs API key (yoksa Enter): ")
  if [ -n "$K" ]; then setenv ELEVEN_API_KEY "$K"; V=$(ask "ElevenLabs voice ID (boş = varsayılan): "); [ -n "$V" ] && setenv ELEVEN_VOICE_ID "$V"; fi
fi

say_ "7/8  Anahtarlar GitHub'a (gizli olarak) yükleniyor…"
for K in CLAUDE_CODE_OAUTH_TOKEN IG_ACCESS_TOKEN IG_USER_ID TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID AZURE_SPEECH_KEY AZURE_SPEECH_REGION ELEVEN_API_KEY ELEVEN_VOICE_ID GOOGLE_TTS_API_KEY; do
  V=$(getenv "$K"); [ -n "$V" ] && gh secret set "$K" -R "$OWNER/$REPO" -b "$V" >/dev/null && echo "  ✔ $K"
done
git add -A >/dev/null; git -c user.name="setup" -c user.email="setup@local" commit -qm "kurulum" >/dev/null 2>&1 || true; git push -q origin main 2>/dev/null || true

say_ "8/8  İlk prova başlatılıyor (Instagram'a GÖNDERMEZ, Telegram'a video gelir)…"
for i in 1 2 3 4 5 6; do
  if gh workflow run daily.yml -R "$OWNER/$REPO" -f dry_run=true >/dev/null 2>&1; then echo "✔ Başladı. 10-15 dakika içinde Telegram'a mesajlar ve video gelecek."; break; fi
  sleep 10
done
echo
echo "İzlemek için: https://github.com/$OWNER/$REPO/actions"
echo "Prova iyi gittiyse artık her sabah 07:40'ta kendi kendine çalışır ve ~08:00'de paylaşır."
echo "Bugün hemen gerçek paylaşım istiyorsanız:  gh workflow run daily.yml -R $OWNER/$REPO"
