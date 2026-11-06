#include <stdio.h>
#include <string.h>

#define SENSORES 1
#define HORAS 24
#define TAM_NOME 24

#define LIMITE_CO2 1000.0f
#define MEDIA_CRITICA 1300.0f

#define PPM_MINIMO 200.0f
#define PPM_MAXIMO 10000.0f

int ler_amostra(float *ppm, int *descartadas);
int coletar_historico(float matriz[][HORAS], char nomes[][TAM_NOME], int linhas, int colunas);
void analisar_co2(float matriz[][HORAS], char nomes[][TAM_NOME], int linhas, int colunas);

int main(void) {
    float historico_co2[SENSORES][HORAS];
    char nomes[SENSORES][TAM_NOME] = {"Agrosense"};

    if (!coletar_historico(historico_co2, nomes, SENSORES, HORAS)) {
        fprintf(stderr, "\nERRO: coleta incompleta, o painel nao foi gerado.\n");
        fprintf(stderr, "Verifique se o Arduino esta conectado e se a porta esta correta.\n");
        return 1;
    }

    analisar_co2(historico_co2, nomes, SENSORES, HORAS);

    return 0;
}

int ler_amostra(float *ppm, int *descartadas) {
    for (;;) {
        int lidos = scanf("%f", ppm);

        if (lidos == 1) {
            if (*ppm >= PPM_MINIMO && *ppm <= PPM_MAXIMO) {
                return 1;
            }
            (*descartadas)++;
            fprintf(stderr, "  descartada, fora da faixa fisica: %.1f PPM\n", *ppm);
            continue;
        }

        if (lidos == EOF) {
            return 0;
        }

        if (getchar() == EOF) {
            return 0;
        }
    }
}

int coletar_historico(float matriz[][HORAS], char nomes[][TAM_NOME], int linhas, int colunas) {
    int descartadas = 0;
    int total = linhas * colunas;

    fprintf(stderr, "=== ECOTECH MONITOR: COLETA COM SENSOR REAL (MH-Z19B) ===\n");
    fprintf(stderr, "%d estufa(s) x %d amostras = %d leituras\n", linhas, colunas, total);
    fprintf(stderr, "A 2 s por amostra, cerca de %d s por setor.\n\n", colunas * 2);

    for (int i = 0; i < linhas; i++) {
        fprintf(stderr, ">>> POSICIONE O SENSOR EM: %s\n", nomes[i]);

        for (int j = 0; j < colunas; j++) {
            if (!ler_amostra(&matriz[i][j], &descartadas)) {
                fprintf(stderr, "\nA entrada terminou com %d de %d leituras.\n",
                        i * colunas + j, total);
                return 0;
            }

            fprintf(stderr, "  [%-22s] amostra %2d/%d: %7.1f PPM\n",
                    nomes[i], j + 1, colunas, matriz[i][j]);
        }

        fprintf(stderr, "  setor %s concluido\n\n", nomes[i]);
    }

    if (descartadas > 0) {
        fprintf(stderr, "Leituras descartadas por estarem fora da faixa: %d\n", descartadas);
    }
    fprintf(stderr, "Coleta completa. Gerando painel...\n\n");

    return 1;
}

void analisar_co2(float matriz[][HORAS], char nomes[][TAM_NOME], int linhas, int colunas) {
    float maior_co2 = matriz[0][0];
    int pos_sensor = 0;
    int pos_amostra = 0;

    float pior_media = 0.0f;
    int pior_setor = 0;

    char status[10];

    printf("=== ECOTECH MONITOR: QUALIDADE DO AR (CO2) ===\n");
    printf("Leitura real - sensor MH-Z19B via Arduino\n");
    printf("Historico coletado: %d estufa(s) x %d amostras (PPM)\n\n", linhas, colunas);

    printf("%-22s %12s %14s   %s\n", "SETOR", "MEDIA (PPM)", "ACIMA DE 1000", "STATUS");
    printf("-----------------------------------------------------------\n");

    for (int i = 0; i < linhas; i++) {
        float soma = 0.0f;
        int leituras_toxicas = 0;
        float media;

        for (int j = 0; j < colunas; j++) {
            soma += matriz[i][j];

            if (matriz[i][j] > LIMITE_CO2) {
                leituras_toxicas++;
            }

            if (matriz[i][j] > maior_co2) {
                maior_co2 = matriz[i][j];
                pos_sensor = i;
                pos_amostra = j;
            }
        }

        media = soma / colunas;

        if (media >= MEDIA_CRITICA) {
            strcpy(status, "CRITICO");
        } else if (media >= LIMITE_CO2) {
            strcpy(status, "ALERTA");
        } else {
            strcpy(status, "IDEAL");
        }

        printf("%-22s %12.2f %14d   %s\n", nomes[i], media, leituras_toxicas, status);

        if (i == 0 || media > pior_media) {
            pior_media = media;
            pior_setor = i;
        }
    }

    printf("-----------------------------------------------------------\n");

    printf("\nALERTA DE TOXIDADE: pico de %.1f PPM em %s (amostra %d)\n",
           maior_co2, nomes[pos_sensor], pos_amostra);
    printf("SETOR MAIS COMPROMETIDO: %s, com media de %.2f PPM\n",
           nomes[pior_setor], pior_media);

    if (pior_media >= MEDIA_CRITICA) {
        printf("RECOMENDACAO: acionar exaustao imediata em %s\n", nomes[pior_setor]);
    } else {
        printf("RECOMENDACAO: manter ventilacao em regime normal\n");
    }
}
