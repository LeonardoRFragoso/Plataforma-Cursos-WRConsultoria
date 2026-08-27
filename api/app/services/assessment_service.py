"""Final learning-assessment rules for the WR NR demo courses.

The NR-01 Annex II requires the pedagogical project to define an evaluation
of learning. The demo uses a versioned, deterministic multiple-choice bank
for the courses that already have complete video content in private storage.
Correct alternatives never leave the backend.
"""

MINIMUM_SCORE = 70.0
QUESTION_VERSION = "wr-nr-demo-v1"


QUESTION_BANKS = {
    "NR-06-F": [
        {
            "id": "nr06-q1",
            "prompt": "Qual é a finalidade principal do Equipamento de Proteção Individual (EPI)?",
            "options": [
                "Eliminar toda necessidade de medidas coletivas",
                "Proteger o trabalhador contra riscos que possam ameaçar sua segurança e saúde",
                "Substituir procedimentos de trabalho seguro",
                "Dispensar treinamento sobre riscos ocupacionais",
            ],
            "correct": 1,
        },
        {
            "id": "nr06-q2",
            "prompt": "Em relação ao fornecimento de EPI adequado ao risco, qual conduta é esperada do empregador?",
            "options": [
                "Cobrar do trabalhador o valor integral do equipamento",
                "Fornecer apenas quando houver acidente anterior",
                "Fornecer gratuitamente EPI adequado ao risco e em condições de uso",
                "Permitir qualquer equipamento sem considerar sua adequação",
            ],
            "correct": 2,
        },
        {
            "id": "nr06-q3",
            "prompt": "Qual é uma responsabilidade do trabalhador quanto ao EPI recebido?",
            "options": [
                "Usá-lo para a finalidade a que se destina e zelar por sua conservação",
                "Modificar o equipamento sempre que desejar",
                "Emprestá-lo sem qualquer controle",
                "Ignorar danos que comprometam sua proteção",
            ],
            "correct": 0,
        },
        {
            "id": "nr06-q4",
            "prompt": "A escolha do EPI deve considerar principalmente:",
            "options": [
                "Somente a preferência estética do usuário",
                "O risco ocupacional, a atividade e a proteção necessária",
                "A marca mais conhecida, independentemente do risco",
                "A possibilidade de substituir todos os controles coletivos",
            ],
            "correct": 1,
        },
        {
            "id": "nr06-q5",
            "prompt": "Ao identificar dano ou perda de eficiência do EPI, o trabalhador deve:",
            "options": [
                "Continuar usando até o fim do turno sem informar ninguém",
                "Comunicar a situação para que sejam tomadas as providências cabíveis",
                "Descartar o equipamento em qualquer local",
                "Reparar por conta própria mesmo sem autorização",
            ],
            "correct": 1,
        },
    ],
    "NR-12-F": [
        {
            "id": "nr12-q1",
            "prompt": "Qual é o objetivo das proteções e dispositivos de segurança em zonas de perigo de máquinas?",
            "options": [
                "Aumentar exclusivamente a velocidade de produção",
                "Impedir ou reduzir a exposição do trabalhador aos perigos",
                "Substituir toda capacitação dos operadores",
                "Permitir acesso livre às partes móveis",
            ],
            "correct": 1,
        },
        {
            "id": "nr12-q2",
            "prompt": "Antes de intervenção de manutenção em uma máquina, a conduta segura inclui:",
            "options": [
                "Manter as fontes de energia ativas para ganhar tempo",
                "Parar a máquina e controlar as fontes de energia conforme o procedimento",
                "Retirar todas as proteções definitivamente",
                "Solicitar que outro trabalhador segure as partes móveis",
            ],
            "correct": 1,
        },
        {
            "id": "nr12-q3",
            "prompt": "O dispositivo de parada de emergência deve ser entendido como:",
            "options": [
                "Um recurso complementar para situações de emergência, e não substituto das demais proteções",
                "O único sistema de segurança necessário",
                "Um comando de produção normal",
                "Um item facultativo em qualquer máquina",
            ],
            "correct": 0,
        },
        {
            "id": "nr12-q4",
            "prompt": "Quem deve operar ou intervir em máquinas e equipamentos?",
            "options": [
                "Qualquer pessoa disponível no setor",
                "Somente trabalhadores autorizados e capacitados para a atividade",
                "Apenas visitantes acompanhados",
                "Somente quem já sofreu acidente com a máquina",
            ],
            "correct": 1,
        },
        {
            "id": "nr12-q5",
            "prompt": "Uma proteção de máquina pode ser retirada durante a operação normal quando:",
            "options": [
                "O operador considerar mais confortável",
                "A produção estiver atrasada",
                "Nunca, salvo condições previstas em procedimento seguro de intervenção com os controles aplicáveis",
                "Houver apenas um trabalhador no setor",
            ],
            "correct": 2,
        },
    ],
    "NR-33-AUT": [
        {
            "id": "nr33-q1",
            "prompt": "Um espaço confinado é caracterizado, entre outros aspectos, por:",
            "options": [
                "Ser projetado para ocupação humana contínua",
                "Possuir meios limitados de entrada e saída e não ser projetado para ocupação contínua",
                "Ser necessariamente um ambiente subterrâneo",
                "Não apresentar qualquer risco atmosférico",
            ],
            "correct": 1,
        },
        {
            "id": "nr33-q2",
            "prompt": "Antes da entrada em espaço confinado, deve existir controle formal da entrada por meio de:",
            "options": [
                "Autorização verbal informal",
                "Permissão de Entrada e Trabalho e procedimentos aplicáveis",
                "Mensagem particular entre trabalhadores",
                "Apenas registro de ponto",
            ],
            "correct": 1,
        },
        {
            "id": "nr33-q3",
            "prompt": "Por que a atmosfera do espaço confinado deve ser avaliada e monitorada conforme o procedimento?",
            "options": [
                "Para identificar condições perigosas como deficiência de oxigênio ou presença de contaminantes",
                "Somente para medir a temperatura externa",
                "Apenas para definir o horário de almoço",
                "Para dispensar medidas de emergência",
            ],
            "correct": 0,
        },
        {
            "id": "nr33-q4",
            "prompt": "O trabalhador autorizado deve entrar no espaço confinado quando:",
            "options": [
                "Quiser concluir a tarefa rapidamente, mesmo sem autorização",
                "As condições e controles previstos para a entrada estiverem atendidos",
                "Não houver comunicação disponível",
                "O vigia tiver abandonado o posto",
            ],
            "correct": 1,
        },
        {
            "id": "nr33-q5",
            "prompt": "Em uma emergência em espaço confinado, a resposta deve seguir:",
            "options": [
                "Improvisação do primeiro trabalhador disponível",
                "O plano e os procedimentos de emergência e resgate definidos",
                "Entrada imediata de qualquer colega sem proteção",
                "Somente comunicação após o término do trabalho",
            ],
            "correct": 1,
        },
    ],
    "NR-35-F": [
        {
            "id": "nr35-q1",
            "prompt": "Para fins da NR-35, o trabalho em altura envolve atividade executada acima de qual nível inferior quando houver risco de queda?",
            "options": ["1 metro", "2 metros", "3 metros", "5 metros"],
            "correct": 1,
        },
        {
            "id": "nr35-q2",
            "prompt": "Antes da realização do trabalho em altura, a organização deve considerar:",
            "options": [
                "Somente o tempo previsto para a tarefa",
                "A análise dos riscos e as medidas de prevenção aplicáveis",
                "A preferência individual por determinado equipamento",
                "A eliminação dos procedimentos de emergência",
            ],
            "correct": 1,
        },
        {
            "id": "nr35-q3",
            "prompt": "Quando utilizado sistema de proteção individual contra quedas, seus componentes devem:",
            "options": [
                "Ser selecionados e utilizados de forma compatível com os riscos e o sistema previsto",
                "Ser escolhidos apenas pela cor",
                "Ser compartilhados sem inspeção",
                "Substituir automaticamente todas as medidas de proteção coletiva",
            ],
            "correct": 0,
        },
        {
            "id": "nr35-q4",
            "prompt": "Se surgirem condições que tornem o trabalho em altura inseguro, a atividade deve:",
            "options": [
                "Continuar até o fim do turno",
                "Ser interrompida até que as condições de segurança sejam restabelecidas",
                "Prosseguir sem comunicação",
                "Ser acelerada para reduzir o tempo de exposição",
            ],
            "correct": 1,
        },
        {
            "id": "nr35-q5",
            "prompt": "O planejamento de emergência para trabalho em altura deve considerar:",
            "options": [
                "Apenas primeiros socorros administrativos",
                "Procedimentos e recursos para resposta e resgate compatíveis com os cenários previstos",
                "Somente o acionamento de terceiros sem planejamento",
                "Nenhuma medida específica quando houver EPI",
            ],
            "correct": 1,
        },
    ],
}


def course_requires_assessment(course_code: str) -> bool:
    return course_code in QUESTION_BANKS


def public_questions(course_code: str) -> list[dict]:
    return [
        {"id": item["id"], "prompt": item["prompt"], "options": list(item["options"])}
        for item in QUESTION_BANKS.get(course_code, [])
    ]


def grade_answers(course_code: str, answers: dict[str, int]) -> tuple[int, int, float, bool]:
    bank = QUESTION_BANKS.get(course_code)
    if not bank:
        raise ValueError("Assessment is not configured for this course")
    correct = sum(1 for item in bank if answers.get(item["id"]) == item["correct"])
    total = len(bank)
    score = round((correct / total) * 100, 2) if total else 0.0
    return correct, total, score, score >= MINIMUM_SCORE
