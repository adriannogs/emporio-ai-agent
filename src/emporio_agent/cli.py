import argparse
from .database import initialize_database
from .agent import EmporioAgent

def main():
    parser=argparse.ArgumentParser(description="Assistente virtual da Empório da Música")
    parser.add_argument("--rebuild-db",action="store_true",help="Recria o SQLite a partir dos CSVs")
    parser.add_argument("--no-llm",action="store_true",help="Usa somente respostas determinísticas")
    parser.add_argument("--session",default="cli",help="Identificador da sessão")
    args=parser.parse_args()
    initialize_database(force=args.rebuild_db)
    agent=EmporioAgent(use_llm=not args.no_llm)
    print("\nEmpório da Música | Assistente virtual")
    print("Digite 'sair' para encerrar. Dados comerciais vêm dos CSVs fornecidos.\n")
    while True:
        try: message=input("Você: ").strip()
        except (EOFError,KeyboardInterrupt):
            print("\nAté mais!"); break
        if message.lower() in {"sair","exit","quit"}: 
            print("Empório da Música: Foi um prazer ajudar! Até a próxima. 🎵"); break
        if not message: continue
        print("\nEmpório da Música:",agent.respond(message,args.session),"\n")

if __name__=="__main__":
    main()
