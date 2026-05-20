import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from youtube.client import YouTubeClient
from sentimento.analyzer import Polarity

VIDEO_ID = "iYVk1CeIs60"


def main() -> None:
    print()
    print(f" Vídeo analisado: https://www.youtube.com/watch?v={VIDEO_ID}")

    client = YouTubeClient()

    # ── Informações do vídeo ─────────────────────────────────────────
    info = client.buscar_info_video(VIDEO_ID)
    if info:
        print(" Informações do Vídeo:")
        print(f"   Título:       {info.titulo}")
        print(f"   Canal:        {info.canal}")
        print(f"   Publicado em: {info.publicado_em}")
        print(f"   Views:        {info.views}")
        print(f"   Likes:        {info.likes}")
        print(f"   Comentários:  {info.total_comentarios}")

    # ── Coleta de comentários ────────────────────────────────────────
    print(f"\n Buscando comentários do vídeo via YouTube Data API...")
    comentarios = client.buscar_comentarios(VIDEO_ID)

    if not comentarios:
        print(" Nenhum comentário encontrado.")
        sys.exit(0)

    print(f"\n Total de comentários coletados: {len(comentarios)}")

    # ── Análise de sentimento ────────────────────────────────────────
    print("\n Analisando sentimento de cada comentário...\n")

    contagem = {"positive": 0, "negative": 0, "neutral": 0}

    for i, com in enumerate(comentarios, start=1):
        # Tokeniza e calcula a polaridade do texto do comentário
        polaridade = Polarity(com.texto)

        # Contabiliza
        if polaridade in contagem:
            contagem[polaridade] += 1

        # Emoji visual para o resultado
        emoji = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}.get(
            polaridade, "❓"
        )

        print("----------------------------")
        print(f"#{i}")
        print(f"Autor:      {com.autor}")
        print(f"Comentário: {com.texto}")
        print(f"Sentimento: {emoji} {polaridade.upper() if polaridade else 'N/A'}")
        print("----------------------------")

    # ── Resumo final ─────────────────────────────────────────────────
    total = len(comentarios)
    print("\n" + "=" * 50)
    print(" RESUMO DA ANÁLISE DE SENTIMENTOS")
    print("=" * 50)
    print(f"  Total de comentários analisados: {total}")
    print(f"  🟢 Positivos:  {contagem['positive']:>4}  ({contagem['positive']/total*100:.1f}%)")
    print(f"  🔴 Negativos:  {contagem['negative']:>4}  ({contagem['negative']/total*100:.1f}%)")
    print(f"  ⚪ Neutros:    {contagem['neutral']:>4}  ({contagem['neutral']/total*100:.1f}%)")
    print("=" * 50)


if __name__ == "__main__":
    main()
