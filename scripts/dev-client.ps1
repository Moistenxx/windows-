$ErrorActionPreference = "Stop"
Push-Location client
if (!(Test-Path node_modules)) {
  npm install
}
npm run dev
Pop-Location
