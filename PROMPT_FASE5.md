# PROMPT — Fase 5: Entrada via texto WhatsApp

Cole no novo chat. Leia os arquivos do projeto antes de codar.

---

## Contexto

Sistema C2 CPChq (Flask + Supabase). Fases 1-4 concluidas. Repo: `c:\Users\watso\gerador_cars_emprego\`

Operadores recebem escala das unidades por WhatsApp em texto semi-padronizado. Hoje transcrevem para xlsx antes de fazer upload. Isso e retrabalho.

## Fluxo novo

1. Operador cola texto de UMA unidade no textarea
2. `POST /api/parse-texto` parseia → retorna `{ cabecalho, fracoes, avisos }`
3. Frontend mostra preview editavel (formulario pre-preenchido)
4. Operador corrige o que o parser errou, confirma
5. Salva no Supabase + renderiza cards (mesmo fluxo do upload xlsx)

Upload xlsx continua como alternativa.

## Etapas

1. **Parser backend** — `app/services/whatsapp_parser.py` com `parse_cabecalho()` e `parse_fracoes()`. Retorna os mesmos tipos `FracaoRow` e `CabecalhoRow` de `xlsx_validator.py`. Usar `sanitize_text`/`safe_int` existentes.
2. **Endpoint API** — `POST /api/parse-texto` em `api.py`. Campo `avisos` lista o que nao conseguiu extrair.
3. **Tela cola-texto** — Botao "Colar texto do WhatsApp" na tela do operador. Textarea + botao "Interpretar".
4. **Preview editavel** — Formulario pre-preenchido. Botoes: adicionar/remover fracao, confirmar e salvar, voltar ao texto.
5. **Testes** — `tests/test_whatsapp_parser.py` com os 7 textos reais abaixo como fixtures. Cada teste deve validar o numero correto de fracoes extraidas.

## O que o parser precisa extrair

**Cabecalho** (bloco numerico no final — formato consistente em todas as unidades):
- Efetivo Total, Oficiais, Sgts, Sds, VTRs, Motos, Ef Motorizado, Armas ACE/Portateis/Longas, Animais, Local, Missoes
- VTRs com motos: `25 + 12 motocicletas` → vtrs=25, motos=12
- Header: unidade (do `*Xo BATALHAO*`), data, oficial superior, COPOM, operadores

**Fracoes** (blocos separados por linha em branco, cada um com Cmt/Equipe/Missao/Horario):
- Detectar inicio de fracao por: nome em CAPS, `Cmt:`, `Xo TURNO`, `N. MISSAO:`
- Ignorar linhas de VTR/tripulacao (`VTR/EQUIPE:`, `MOT:`, `PTR X:`, `TOTAL: XX ME`, `Xo SGT PM: XX`)
- Ignorar titulos de secao (`INFORMACOES GERAIS`, `EQUIPES E EMPREGO`, `Efetivo de Xo e Yo turnos:`)

Os 7 textos abaixo SAO a especificacao do parser. O parser DEVE extrair o numero correto de fracoes de cada um.

## Textos reais (fixtures)

### 1 BPChq — 12 fracoes

```
*DADOS PARA PLANILHA DE COMANDO E CONTROLE DE MEIOS OPERACIONAIS*
*BRIGADA MILITAR*
*CPChq*
*1° BATALHÃO DE POLICIA DE CHOQUE*
*Previsão do dia 08/04/2026*

Oficial Superior CPChq MAJ PM BOSCARDIN (54) 99969 - 3391
COPOM: Qso Funcional (51) 98437-6940
SD PM PAULO
Horário: 06:00 às 18:00
SD PM GLASENAP
Horário: 18:00 às 06:00

PELOTÃO DE PRONTIDÃO
Cmt: TEN PM BATISTA (51) 98542-3634
Equipes: 06 (22 PM's)
Missão: Prontidão, Reserva de OCD, Instrução Centralizada e Combate aos CVLIs – Área do 21º BPM
Horário: 20:00 às 02:00

RESERVA I
Cmt: TEN PM TACIANO (51) 99896-8666
Equipes: (21 PM's)
Missão: Instrução Centralizada
Horário: 08:00 às 18:00

RESERVA II
Cmt: TEN PM RENATO (55) 99645-6325
Equipes: (21 PM's)
Missão: Instrução Centralizada
Horário: 08:00 às 18:00

PATRES MATUTINA
Cmt: SGT PM MÉDRICK (51) 99819-5154
Equipes: 05 (19 PM's)
Missão: PTM e Combate aos CVLIs – Área do 19º BPM
Horário: 10:00 às 16:00

PATRES VESPERTINA
Cmt: TEN PM DANILDO (51) 99856-9978
Equipes: 05 (21 PM's)
Missão: PTM e Combate aos CVLIs – Área do 20º BPM
Horário: 16:00 às 22:00

PATRES VESPERTINA
Cmt: SGT PM FÉO (51) 98108-0300
Equipes: 03 (12 PM's)
Missão: PTM e Combate aos CVLIs – Área do 1º BPM
Horário: 17:00 às 22:00

CANIL I
Cmt: SD PM MANICA (51) 98284-1736
Equipes: 01 (03 PM's)
Missão: Prontidão de Faro
Horário: 07:00 às 07:00

BATEDORES
Cmt: TEN PM RODRIGUES (51) 99156-7477
Equipes: 17 (17 PMs)
Missão: Prontidão
Horário: 08:00 às 20:00

OPERAÇÃO LITORAL
Cmt: SGT PM PEREIRA (51) 99861-1903
Equipes: 03 (12 PM's)
Missão: PTM e Combate aos CVLIs – Área do 8º BPM(Mostardas)
Horário: 13:00 às 00:00

OPERAÇÃO ESCOLA SEGURA I
Cmt: SGT PM SEVERO (51) 98058-6342
Equipes: 01 (03 PM's)
Missão: Operação Fecha Quartel - Escola Segura
Horário: 06:30 às 12:30

OPERAÇÃO ESCOLA SEGURA II
Cmt: SD PM ÁLVARO (51) 99297 - 3153
Equipes: 01 (03 PM's)
Missão: Operação Fecha Quartel - Escola Segura
Horário: 12:30 às 18:30

Data: 08/04/2026
Turno:2/3 e 4/1
1. Efetivo Total: 154
   1.1 Oficial: 05
1.2 Sgt: 30
   1.3 SD: 119
2. VTRs:   25 + 12 motocicletas
3. Efetivo Motorizado: 112
4. Armas de Condução Elétrica Empregadas: 25
5. Armas Portáteis Empregadas: 154
6. Armas Longas Empregadas: 95
7. Local de Atuação: CRPMC/CRPM LITORAL
8. Missões/Osv:  RESERVA DE OCD/PRONTIDÃO/CVLI/PTM/ESCOLA SEGURA/INSTRUÇÃO
9. Animais Empregados:  03 cães
```

### 2 BPChq — 1 fracao (ignorar blocos VTR/tripulacao)

```
*DADOS PARA PLANILHA DE COMANDO E CONTROLE DE MEIOS OPERACIONAIS*
*BRIGADA MILITAR*
*CPChq*
*2° BATALHÃO DE POLICIA DE CHOQUE*
*Previsão do dia 08/04/2026*

Cmt: 1° TEN ANDRÉA Qso :  (55)  99703-4733
Equipes: 04 (15 PMs)
Missão: Patrulhamento Tático Motorizado
Data: 07/04/26 (TER)
Hora de emprego: 19:00 às 07:00

Local de atuação: Santa Maria

VTR/EQUIPE: 14610
CMT: 1° TEN PM ANDREA  id func 2458888
QSO: 55 99703-4733
MOT: SD PM CARLOS
PTR 3: SD PM C. CORRÊA
PTR 4: SD PM ARMANINI

VTR/EQUIPE: 13099
CMT:  1º SGT PM ZANIN Qso: 991577457, id func 2783436
MOT: SD PM LAMPERT
PTR 3: SD PM ROGER
PTR 4: SD PM YAGO

VTR/EQUIPE: 15178
CMT: SD PM VINICIUS func 2971852
Qso: (55) 99715-6715
MOT: SD PM MICHEL
PTR 3: SD PM MARCELO
PTR 4: SD PM BOCK

 VTR/EQUIPE: 13097
CMT: SD PM LORENSI func 2969017
Qso: (55)  99990-1982
MOT: SD PM ALLES
PTR 3: SD PM MULLER
PTR 4: SD PM

  1.Efetivo Total: 15
     1.1. Oficial: 01
     1.2. Sgt: 01
     1.3.  SD: 13
   2. VTRs: 04
3. Efetivo Motorizado: 15
4. Armas de Condução Elétrica Empregadas: 04
5. Armas de Porte Empregadas: 15
6. Armas Longas, Empregadas: 15
7. Local de Atuação: Santa Maria
8. Missões:  PTR
9. Animais Empregadas
```

### 3 BPChq — 3 fracoes (sem nome de fracao, comeca por Cmt:)

```
*DADOS PARA PLANILHA DE COMANDO E CONTROLE DE MEIOS OPERACIONAIS*
*BRIGADA MILITAR*
*CPChq*
*3° BATALHÃO DE POLICIA DE CHOQUE*
*Previsão do dia 08/04/2026*

OF SA 23T -  Cap PM Viganó 54996174666
OF SA 41T - Ten PM Arus  54-99954-2319

Cmt: Sgt PM Ivo 54 991771026
Equipe: 04 (11 PM)
Missão: OP Angico Passo Fundo, Mato Castelhano e Coxilha
Horário de emprego: 07hs às 19h

Cmt: Ten PM Arus 54-99954-2319
Equipe: 02 (08 PM)
Missão: CVLI Passo Fundo e Carazinho
Horário de emprego: 19h às 07h

Cmt: Ten PM Rudinei 54-99152-1460
Equipe: 05 (20 PM)
Missão: Operação XAPARI - IBAMA em Três Passos
Horário de emprego: 06hs as 18hs

1. Efetivo Total: 44
1.1 Oficial: 03
1.2 Sgt: 06
1.3 Sd: 35
2. VTRs: 11
3. Efetivo Motorizado: 40
4. Armas de Condução Elétrica Empregadas: 11
5. Armas Portáteis Empregadas: 44
6. Armas Longas Empregadas: 55
7. Local de Atuação: Passo Fundo,Carazinho, Coxilha, Mato Castelhano, Três Passos
8. 8. Missões/Osv: OSv 0342/P3/CPCHQ/2025, OSv 0407/P3/CPCHQ/2025, OSv 0124/SCmt-G/2026, Osv0235/P3/CPChq/2026
9. Animais Empregados:00
```

### 4 BPChq — 4 fracoes (usa "Xo TURNO" como separador, Of. de SV/Aux. de SV no lugar de Cmt)

```
*DADOS PARA PLANILHA DE COMANDO E CONTROLE DE MEIOS OPERACIONAIS*
*BRIGADA MILITAR*
*CPChq*
*4° BATALHÃO DE POLICIA DE CHOQUE*
*Previsão do dia 08/04/2026*

1º TURNO

Sd PM Jaime
Equipes: (02 PMs)
Missão: Guarda do Batalhão
Data: 08/04/2026
Hora de emprego: 01:30 às 07:30.
Locais de atuação: Caxias do Sul

23º TURNO

Of. de SV: Ten. PM Motta 54981133544
Aux. de SV:
Equipes: 01 (04 PMs)
Missão: Operação Angico
Data: 08/04/2026
Hora de emprego: 07:30 às 19:30
Locais de atuação: Caxias do Sul.

34º TURNO

Of. de SV: Ten Derquis (54)996135222
Aux. de SV: 2° Sgt Zorzi (54)991478118
Equipes: 06  (22 PMs)
Missão: Evento Desportivo
Data: 08/04/2026
Hora de emprego: 14:00 às 02:00.
Locais de atuação: Caxias do Sul,
4º TURNO

Aux. de SV: Sgt PM Kener 51 99956-2470
Equipes: 05 (20 PMs)
Missão: Diária
Data: 08/04/2026
Hora de emprego: 18:00 às 02:00
Locais de atuação: Igrejinha

1. Efetivo Total: 100
1.1. Oficial: 03
1.2. Sgt: 21
1.3. Sd: 76
2. VTRs: 24
3. Efetivo Motorizado: 92
4. Armas de Condução Elétrica Empregadas: 24
5. Armas de Porte Empregadas: 100
6. Armas Longas Empregadas: 71
7. Local de Atuação: Caxias do Sul e Igrejinha.
8. Missões: Guarda ao Batalhão, Policiamento Praça Desportiva e Diária Igrejinha.
9. Animais Empregados: 00
```

### 5 BPChq — 4 fracoes (horarios especiais: "24hs", "Retorno")

```
*DADOS PARA PLANILHA DE COMANDO E CONTROLE DE MEIOS OPERACIONAIS*
*BRIGADA MILITAR*
*CPChq*
*5° BATALHÃO DE POLICIA DE CHOQUE*
*Previsão do dia 08/04/2026*

OF de SV:
Data: 08/04/2026

Efetivo de 2° e 3º turnos:

Cmt: 2ºSgt PM Velasques 53 98102-5834
Equipe: 01 (03PM)
Missão: Fecha quartel (Pelotas)
Horário de emprego: 06:30s as 18:30h

Cmt: 1ºSgt PM Pablo 53 98111-4491
Equipe: 03 (12PM)
Missão: Angico (Pelotas, Morro Redondo e Arroio do Padre)
Horário de emprego: 07hs as 19h

Cmt: 2°Sgt PM Germano 53 99194-4816
Equipe: 04 (16PM)
Missão: Patrulhamento Rural (Jaguarão)
Horário de emprego: 24hs

Cmt: 1°Sgt PM Marlon 53 98459-5715
Equipe: 04 (16PM)
Missão: Patrulhamento Rural (Santa Vitória do Palmar)
Horário de emprego: Retorno

Efetivo de 4° e 1º turnos:

1. Efetivo Total: 47
 1.1 Oficiais: 00
 1.2 Sgt: 17
 1.3 Sd: 30
2. VTRs: 12
3. Efetivo Motorizado: 47
4. Armas de Condução Elétrica Empregadas: 12
5. Armas Portáteis Empregadas: 47
6. Armas Longas Empregadas: 47
7. Local de Atuação: Pelotas, Morro Redondo, Arroio do Padre e Jaguarão.
8. Missões/Osv: OSv.nº 033/P3/26, OSv.nº 037/P3/26, OSv.nº 039/P3/26.
```

### 6 BPChq — 3 fracoes (missao como titulo numerado, bullets *, "Efetivo:" no lugar de "Equipes:")

```
*DADOS PARA PLANILHA DE COMANDO E CONTROLE DE MEIOS OPERACIONAIS*
*BRIGADA MILITAR*
*CPChq*
*6°BPChq*
*Previsão do dia 08/04/2026*

INFORMAÇÕES GERAIS
* DATA: 08 de abril de 2026
* OF de SV: TEN PM CORDEIRO
* Tel: (55)  984273001

EQUIPES E EMPREGO

1. MISSÃO: CVLI/URUGUAIANA
     Cmt: TEN PM SARAIVA
* Tel: (55) 997114104
* Efetivo: 05 Equipes (17 PMs)
* Horário: 13h às 19h

    2. MISSÃO: OP RIB/URUGUAIANA
* Cmt: SGT PM SAULO
* Tel: (55) 996850125
* Efetivo: 02 Equipe (06 PMs)
* Horário: 07h às 19h

3. MISSÃO: CVLI/URUGUAIANA
     Cmt: SGT PM LUIZ PIRES
* Tel: (55) 8148-4355
* Efetivo: 03 Equipes (12 PMs)
* Horário: 19h às 01h

QUADRO DE MEIOS

1. Efetivo Total: 35
1.1 Oficial: 02
1.2 Sgt: 04
1.3 Sd: 29
2. VTRs: 10
3. Efetivo Motorizado: 35
4. Armas de Condução Elétrica Empregadas: 10
5. Armas Portáteis Empregadas: 35
6. Armas Longas Empregadas: 24
7. Local de Atuação: Uruguaiana
8. 8. Missões/Osv: PTM e OP RIB
9. Animais Empregados: 01
```

### 4 RPMon — 10 fracoes (horarios QTL complexos, linhas de graduacao a ignorar)

```
*DADOS PARA PLANILHA DE COMANDO E CONTROLE DE MEIOS OPERACIONAIS*
*BRIGADA MILITAR*
*CPChq*
*4°RPMon*
*Previsão do dia 08/04/2026*

OF de SV: CAP PM GIACOMELLI 55 8425-8355
MOT OF SV: *
VTR: **
Data: 08/04/2026

Cmt: 2° SGT PM SOUTO
Equipe: 01 Equipe (06 PM)
Missão: POLICIAMENTO MONTADO
Horário: QTL: 09h:00min - PREL/DESL 13h:00min - LOCAL: 14h00min - 20h:00min LIB:21h:00min
2º SGT PM: 01
SD PM: 05
TOTAL: 06 ME

Cmt: 2° SGT PM FERREIRA
Equipe: 01 Equipe (04 PM)
Missão: 16º RODEIO INTERNACIONAL E 27º RODEIO CRIOULO DE CAPÃO DA CANOA
Horário: EM QTL: 12h:00min DESL: 14h:00min
2º SGT PM: 01
SD PM: 03
TOTAL: 04 ME

1º Esq - 4° Pel – Santa Maria
Cmt: SD PM RAFAEL
Equipe: 01 Equipe (04PM)
Missão: SV DE CAVALARIÇA
Horário: Das 07h:00min as 19h:00min
2º SGT PM: 00
SD PM: 04
TOTAL: 04 ME

1º Esq – 5°Pel - S. do Livramento
Cmt:  SGT PM OLIVEIRA
Equipe: 03 PM
Missão: PERMANÊNCIA
Horário: 07:00 AS 15:00
2º SGT PM: 01
SD PM: 02
TOTAL: 03

2º Esq – 4°Pel - Passo Fundo
Cmt: 2ºSGT PM TAYLAN
Equipe: 03 PM
Missão:  POLICIAMENTO MONTADO
Horário: QTL: 08H (INSTRUÇÃO/MANUTENÇÃO NAS DEPENDÊNCIAS) PREL/DESLC: 12:30H LOCAL: 13H REC: 19H LIB: 20H
2º SGT PM: 01
SD PM: 02
TOTAL: 03

2º Esq - 5º Pel - Caxias do Sul
Cmt: 2° SGT PM PIRES
Equipe: 01 Equipes (06 PM)
Missão: EVENTO FUTEBOL CAXIAS x JUVENTUDE
Horário: QTL: 10h30 PREL DESL: 14h30 LOCAL: 15h30 LIB: 22h30
2º SGT PM: 02
SD PM: 04
TOTAL: 06

GDA/CUSTÓDIA DE PRESO
Cmt: SD PM BERGER
Equipe: 01 Equipe (03 PM)
Horário: 06:00h às 18:00h
2° SGT PM: 00
SD PM: 03
TOTAL: 03 ME

GDA/CUSTÓDIA DE PRESO
Cmt: SD PM CADUM
Equipe: 01 Equipe (03 PM)
Horário: 18:00h às 06:00h
1° SGT PM: 00
SD PM: 03
TOTAL: 03 ME

3° Esq - Palácio Piratini
Cmt: 2°SGT PME ACACIO
Equipe: 01 Equipe (06 PM)
Horário: 06:00h às 18:00h
2° SGT PM: 01
SD PM: 05
TOTAL: 06 ME

3° Esq - Palácio Piratini
Cmt: 2°SGT PME SILVA
Equipe: 01 Equipe (06 PM)
Horário: 18:00h às 06:00h
2° SGT PM: 01
SD PM: 05
TOTAL: 06 ME

Efetivo Total: 46
1.1 OFICIAL: 01
1.2 SGT: 8
1.3 SD: 37
2. VTRs: 03
3. Efetivo Motorizado: 03
4. Armas de Condução Elétrica Empregadas: 02
5. Armas Portáteis Empregadas: 46
6. Armas Longas Empregadas: 00
7. Local de Atuação: Porto Alegre/ Santa Maria/ S. Do Livramento/ Caxias do Sul/ Passo Fundo
8. Missões: ORDEM DE SERVIÇO Nº 001/P3-RBG/2026,...
9. Animais Empregados: 16 CAVALOS
```

---

## Principios

1. Tipagem forte, max 500 LOC/arquivo, sanitize_text em todo input
2. Front burro, logica no backend
3. Design: mesma identidade visual (preto #000, laranja #F7B900, branco #FFF, cinza #57575A)
4. Implemente na ordem: parser → API → tela cola → preview → testes
5. Upload xlsx deve continuar funcionando
