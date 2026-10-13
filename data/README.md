# Dados locais

Os arquivos das duas cidades estão nos caminhos abaixo, relativos à pasta `data/`.

| Cidade | OSM | GTFS | Overture | Limite municipal |
| --- | --- | --- | --- | --- |
| Ponta Grossa | `raw/ponta_grossa/osm/ponta_grossa.osm.pbf` | `raw/ponta_grossa/gtfs/ponta_grossa_gtfs.zip` | `raw/ponta_grossa/overture/places.parquet` | `raw/ponta_grossa/boundary/municipality.geojson` |
| Curitiba | `raw/curitiba/osm/curitiba.osm.pbf` | `raw/curitiba/gtfs/curitiba_gtfs.zip` | `raw/curitiba/overture/places.parquet` | `raw/curitiba/boundary/municipality.geojson` |

Os limites municipais foram extraídos do ZIP `ibge_limites_municipios.zip` fornecido pelo usuário, pelos códigos IBGE 4119905 e 4106902, e convertidos de EPSG:4674 para GeoJSON em EPSG:4326. O OSM foi extraído de `sul-261012.osm.pbf` com `osmium extract --strategy=complete_ways`. Os POIs são recortes Overture Places em GeoParquet, baixados por bounding box.

A área de estudo em cada YAML é o retângulo dos percentis 1–99 das paradas GTFS dentro do município, acrescido de 2 km. O OSM tem mais 5 km de margem em torno dessa área; o Overture, mais 2 km. A malha hexagonal será gerada localmente com raio de 300 m. O limite municipal pode ser usado para descartar hexágonos fora da cidade; o retângulo sozinho não representa o limite administrativo.

O GTFS permanece compactado. Ponta Grossa usa 2026-10-15 às 08:00 como data de referência com viagens verificadas. Curitiba usa sempre 2026-10-01 às 08:00, também com viagens verificadas. Essa data está dentro do período declarado pelo feed de Curitiba (2026-09-28 a 2026-10-05) e é reutilizada indefinidamente como cenário fixo, sem consultar a data atual. Os resultados não representam horários atuais fora daquele cenário.

Mantenha nomes diferentes para os arquivos GTFS de cada cidade. O r5py usa o nome do arquivo no cache; dois feeds chamados `gtfs.zip` podem ser confundidos.

Preencha e confira os destinos em `config/destinations.yaml`, incluindo os de Curitiba, antes dos pré-cálculos. Revise o catálogo em `config/poi_catalog.yaml` de acordo com as categorias presentes no Overture baixado.

Os scripts de preparação geram em `processed/<cidade>/`: `grid.parquet`, `pois.parquet`, `poi_access.parquet` e `destination_access.parquet`. Os quatro arquivos já foram gerados para Ponta Grossa. Para Curitiba, a malha e os POIs estão prontos; o roteamento foi verificado em uma célula, mas o pré-cálculo completo ainda não foi executado.
