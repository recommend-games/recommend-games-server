#!/usr/bin/env bash

set -euxo pipefail

IN_FILE="${1}"
OUT_FILE="${2}"

if [[ ! -s "${IN_FILE}" ]]; then
	echo "Input file <${IN_FILE}> does not exist, aborting..."
	exit 1
fi

if [[ ${OUT_FILE: -1} == '/' ]]; then
	F=$(basename "${IN_FILE}")
	OUT_FILE="${OUT_FILE}${F:0:4}${F:5:2}${F:8:2}-000000.csv"
fi

echo "Reading from <${IN_FILE}>, writing to <${OUT_FILE}>..."

mkdir --parents "$(dirname "${OUT_FILE}")"

echo 'rank,bgg_id,score' > "${OUT_FILE}"
csvcut --columns 'Rank,ID,Bayes average' "${IN_FILE}" | csvsort --columns 'Rank' | tail -n +2 >> "${OUT_FILE}"

echo "Done."
