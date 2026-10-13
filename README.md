# Localy

MVP de recomendação de regiões por acessibilidade. A Etapa 1 prepara uma malha hexagonal e calcula tempos de caminhada e transporte público de forma determinística.

## Preparação dos dados

Requisitos: Python conforme `pyproject.toml` e JDK 21 ou superior. Os arquivos de entrada e sua origem estão descritos em [data/README.md](data/README.md).

Na raiz do projeto:

```bash
uv run python -m scripts.prepare_data --city ponta_grossa
uv run python -m scripts.precompute_accessibility --city ponta_grossa --max-memory 4G
```

O primeiro comando gera `grid.parquet` e `pois.parquet`. O segundo gera `destination_access.parquet` e `poi_access.parquet`. Ambos usam a mesma configuração para outras cidades, por exemplo `--city curitiba`.

Para conferir uma célula sem alterar os arquivos completos:

```bash
uv run python -m scripts.precompute_accessibility \
  --city ponta_grossa \
  --cell-id ponta_grossa_16054_1126 \
  --output /tmp/localy-check \
  --max-memory 4G
```

Tempos ausentes indicam que nenhum trajeto foi encontrado dentro do limite: 30 minutos para POIs e 60 para destinos. O modo `TRANSIT` do r5py também considera caminhada direta; `best_minutes` guarda o menor valor entre as consultas de caminhada e de transporte.

Curitiba usa sempre 01/10/2026 às 08:00 como cenário de referência, mesmo depois do fim da validade declarada do GTFS. Não é necessário atualizar o feed para repetir este cenário. Os resultados são uma fotografia dos horários fornecidos, não uma previsão de viagens na data atual. O r5py constrói a rede dentro do processo Python: nenhum serviço separado precisa ser iniciado.
