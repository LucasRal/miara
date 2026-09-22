#!/usr/bin/env bash
# Hook de déploiement certbot : rechargé après CHAQUE renouvellement réussi.
# Sans lui, nginx continuerait de servir l'ancien certificat jusqu'au prochain
# redémarrage — c'est-à-dire potentiellement après son expiration.
# Installé dans /etc/letsencrypt/renewal-hooks/deploy/ par setup_vps.sh.
set -euo pipefail
systemctl reload nginx
