handler = SSUBouquetHandler()

# Neue Bouquets anlegen (beide)
handler.createSSUBouquet(
    tv_services=["1:0:1:281D:3FB:1:C00000:0:0:0:"],      # ARD HD
    radio_services=["1:0:2:6DCA:44D:1:C00000:0:0:0:"]   # WDR 2
)

# Später weitere Services anhängen (beide gleichzeitig)
handler.appendToSSUBouquet(
    tv_services=["1:0:1:6DCA:44D:1:C00000:0:0:0:"],     # Beispiel weiterer TV-Service
    radio_services=["1:0:2:2B5C:441:1:C00000:0:0:0:"],  # Beispiel weiterer Radiosender
    append_at_end=True
)
