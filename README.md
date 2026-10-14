# Localy

MVP de recomendação de regiões por acessibilidade. A preparação gera uma malha hexagonal e tempos de caminhada e transporte público; a interface interpreta a consulta e pontua as células sem refazer o roteamento.

## Preparação dos dados

Requisitos: Python conforme `pyproject.toml` e JDK 21 ou superior. Os arquivos de entrada ficam em `data/raw/<cidade>/`.

Na raiz do projeto:

```bash
uv run python -m scripts.prepare_data --city ponta_grossa
uv run python -m scripts.precompute_accessibility --city ponta_grossa --max-memory 4G
```

O primeiro comando gera `grid.parquet` e `pois.parquet`. O segundo gera `destination_access.parquet` e `poi_access.parquet`. Ambos usam a mesma configuração para outras cidades, por exemplo `--city curitiba`.

O catálogo em `config/poi_catalog.yaml` contém 33 tipos de POI, sendo 23 secundários (como padaria, banco, pet shop, galeria de arte e teatro). Esses tipos também são pré-calculados, mas a IA só deve escolhê-los quando forem relevantes para a consulta. Temas amplos, como arte e cultura, podem combinar vários tipos complementares com pesos diferentes; as associações ficam em `config/poi_themes.yaml`. Novos tipos e suas categorias Overture podem ser acrescentados ao catálogo.

`config/overture.yaml` controla a qualidade mínima dos registros: `min_confidence: 0.0` inclui também POIs de baixa confiança positiva, e `include_missing_confidence: true` inclui registros sem esse campo. Registros com confiança zero ou status `permanently_closed` são sempre excluídos. A confiança do Overture estima a existência do local; não é o peso nem a importância do serviço para a pessoa. Ao mudar o catálogo ou o filtro, rode novamente `scripts.prepare_data` e `scripts.precompute_accessibility --part pois` para cada cidade.

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

## Etapa 2: interpretação e pontuação

Com `GEMINI_API_KEY` no arquivo `.env`, analise uma pergunta assim:

```bash
uv run python -m scripts.analyze_query \
  --city ponta_grossa \
  --query "Vou estudar na UTFPR. Quero mercado perto e faço academia."
```

O comando mostra os critérios estruturados, a explicação e as cinco células mais bem avaliadas. Para salvar todos os scores em GeoParquet, acrescente `--output /tmp/localy-scores.parquet`. A interpretação usa o Gemini; a pontuação lê somente os Parquets locais e não inicia o r5py. Os pesos devem ser inteiros de 1 a 5, e destinos/tipos inexistentes são rejeitados. Há apenas uma tentativa de correção quando a resposta da IA é inválida.

Ponta Grossa e Curitiba têm malha de raio 250 m e arquivos de acessibilidade completos. O pré-cálculo dos POIs agora registra também o ID e o nome do lugar com menor tempo de caminhada, quando informado pelo Overture.

Os testes determinísticos da Etapa 2 podem ser executados sem chamada à API:

```bash
uv run python -m unittest scripts.test_phase2 -v
```

O catálogo, os filtros do Overture e os Parquets pré-calculados podem ser verificados com `uv run python -m unittest scripts.test_overture -v`.

## Etapa 3: interface e mapa

Inicie a aplicação na raiz do projeto:

```bash
uv run streamlit run app.py
```

Abra o endereço local indicado pelo Streamlit, selecione a cidade, escreva uma consulta e clique em **Explorar regiões**. A lateral mostra os critérios e pesos. Por padrão, o mapa exibe apenas os 10% melhores hexágonos com pontuação positiva, em verde translúcido e sem bordas; o controle acima do mapa permite variar a faixa de 5% a 25% sem nova chamada à IA. Passe o cursor sobre uma célula para ver os destinos, nomes dos POIs encontrados e tempos. O mapa-base da Carto e a API Gemini precisam de conexão com a internet; o r5py não é iniciado pela interface.

O modelo padrão é `gemini-3.5-flash-lite`. Se desejar, defina `GEMINI_MODEL` no `.env` para usar outro modelo compatível com saída estruturada. Uma resposta 503 do Gemini indica indisponibilidade temporária do serviço; tente novamente.

Para testar a interface e o mapa sem consumir a API:

```bash
uv run python -m unittest scripts.test_phase3 -v
```
