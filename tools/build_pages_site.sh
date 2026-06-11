#!/usr/bin/env bash
set -euo pipefail

out_dir="${1:-_site}"

copy_file() {
  local src="$1"
  local dest="$2"
  if [[ ! -f "$src" ]]; then
    echo "Missing required file: $src" >&2
    exit 1
  fi
  mkdir -p "$(dirname "$dest")"
  cp "$src" "$dest"
}

copy_dir() {
  local src="$1"
  local dest="$2"
  if [[ ! -d "$src" ]]; then
    echo "Missing required directory: $src" >&2
    exit 1
  fi
  rm -rf "$dest"
  cp -R "$src" "$dest"
}

rm -rf "$out_dir"
mkdir -p "$out_dir"

copy_file home.html "$out_dir/index.html"
copy_dir dao-system "$out_dir/dao-system"
copy_dir mstr-mnav "$out_dir/mstr-mnav"
copy_file btc-macro-system/outputs/report.html "$out_dir/macro-report.html"
copy_file btc-macro-system/outputs/latest.json "$out_dir/latest.json"
copy_file market-temperature.html "$out_dir/market-temperature.html"
copy_file investment-thesis-rerun.html "$out_dir/investment-thesis-rerun.html"
copy_file mstr-education.html "$out_dir/mstr-education.html"
copy_file crcl-education.html "$out_dir/crcl-education.html"
copy_file nvda-education.html "$out_dir/nvda-education.html"
copy_file crcl-floor-report.html "$out_dir/crcl-floor-report.html"
copy_file nvda-factory-report.html "$out_dir/nvda-factory-report.html"
copy_file investment-thesis-harness/outputs/report.html "$out_dir/investment-research.html"
copy_file investment-thesis-harness/outputs/latest.json "$out_dir/investment-latest.json"
copy_dir everydayzen-macro "$out_dir/everydayzen-macro"
copy_dir saas-signals "$out_dir/saas-signals"
copy_dir market-top-triggers "$out_dir/market-top-triggers"
copy_dir smallcap-futures-system "$out_dir/smallcap-futures-system"
copy_dir major-futures-system "$out_dir/major-futures-system"
copy_dir lab-scenario-simulator "$out_dir/lab-scenario-simulator"
copy_file price-ladder-short-demo.html "$out_dir/price-ladder-short-demo.html"
copy_file price-ladder-short-theory.html "$out_dir/price-ladder-short-theory.html"
copy_file binance-hot-ladder-lab.html "$out_dir/binance-hot-ladder-lab.html"
copy_file binance-upside-lab.html "$out_dir/binance-upside-lab.html"
copy_file epic-trade-map.html "$out_dir/epic-trade-map.html"
copy_file btc-usdt-ladder-demo.html "$out_dir/btc-usdt-ladder-demo.html"
copy_file btc-usdt-ladder-theory.html "$out_dir/btc-usdt-ladder-theory.html"
copy_file btc-ma95-hybrid-strategy.html "$out_dir/btc-ma95-hybrid-strategy.html"
copy_dir btc-cta "$out_dir/btc-cta"

# NVIDIA 生态链研究包 + BTC 宏观引力图
copy_file nvidia-research.html "$out_dir/nvidia-research.html"
copy_dir assets "$out_dir/assets"
for f in nvidia-ecosystem-complete-framework-2026.md \
         nvidia-ecosystem-watchlist-2026.md \
         nvidia-core-a-financial-teardown-2026.md \
         nvidia-pdd-apple-comparison-2026.md \
         nvidia-ecosystem-company-diligence-template.md \
         nvidia-ecosystem-scorecard-2026.csv \
         nvidia-ecosystem-map-2026.svg nvidia-ecosystem-map-2026.png \
         nvidia-finance-logic-2026.svg nvidia-finance-logic-2026.png \
         nvidia-core-a-financial-teardown-2026.svg nvidia-core-a-financial-teardown-2026.png \
         nvidia-pdd-apple-comparison-2026.svg nvidia-pdd-apple-comparison-2026.png \
         nvidia-vs-pdd-comparison-2026.svg nvidia-vs-pdd-comparison-2026.png \
         btc-macro-gravity-map-2026.svg btc-macro-gravity-map-2026.png; do
  copy_file "$f" "$out_dir/$f"
done

if [[ -f btc-macro-system/data/history/observations.jsonl ]]; then
  copy_file btc-macro-system/data/history/observations.jsonl "$out_dir/observations.jsonl"
fi

if [[ -f investment-thesis-harness/data/history/thesis_snapshots.jsonl ]]; then
  copy_file investment-thesis-harness/data/history/thesis_snapshots.jsonl "$out_dir/thesis-snapshots.jsonl"
fi

touch "$out_dir/.nojekyll"
