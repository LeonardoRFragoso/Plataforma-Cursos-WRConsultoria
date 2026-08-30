"""Final learning-assessment rules for the WR NR demo courses.

The NR-01 Annex II requires the pedagogical project to define an evaluation
of learning. The demo uses a versioned, deterministic multiple-choice bank
for the courses that already have complete video content in private storage.
Correct alternatives never leave the backend.
"""

MINIMUM_SCORE = 60.0
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
    "NR-10-B": [
        {
            "id": "nr10b-q1",
            "prompt": "A NR 10 estabelece requisitos e condições mínimas para garantir a segurança e a saúde dos trabalhadores que interajam com:",
            "options": [
                "Apenas equipamentos de proteção individual",
                "Instalações elétricas e serviços em eletricidade",
                "Máquinas e equipamentos industriais",
                "Trabalho em altura e espaços confinados",
            ],
            "correct": 1,
        },
        {
            "id": "nr10b-q2",
            "prompt": "Entre os riscos em instalações e serviços com eletricidade abordados pela NR 10, destaca-se:",
            "options": [
                "Exposição a ruído contínuo",
                "Choque elétrico, arcos elétricos e queimaduras",
                "Vibração de membros superiores",
                "Iluminação deficiente apenas",
            ],
            "correct": 1,
        },
        {
            "id": "nr10b-q3",
            "prompt": "Antes de intervenções em instalações elétricas, a medida de controle fundamental consiste em:",
            "options": [
                "Manter a instalação energizada para ganhar tempo",
                "Desenergizar a instalação e adotar procedimentos de bloqueio e sinalização",
                "Afastar todos os trabalhadores sem qualquer procedimento",
                "Utilizar apenas EPI, sem desenergizar a instalação",
            ],
            "correct": 1,
        },
        {
            "id": "nr10b-q4",
            "prompt": "Em relação ao profissional que interage com instalações elétricas, a NR 10 exige que ele seja:",
            "options": [
                "Apenas qualificado, independentemente de treinamento",
                "Qualificado, habilitado, capacitado ou autorizado, conforme o caso",
                "Somente autorizado pelo empregador, sem capacitação",
                "Habilitado exclusivamente por experiência prática",
            ],
            "correct": 1,
        },
        {
            "id": "nr10b-q5",
            "prompt": "Em acidente elétrico, a primeira ação de primeiros socorros deve ser:",
            "options": [
                "Tocar a vítima diretamente para avaliar o pulso",
                "Desligar imediatamente a fonte de energia antes de qualquer contato com a vítima",
                "Mover a vítima sem verificar a fonte de energia",
                "Aguardar o socorro sem isolar o local",
            ],
            "correct": 1,
        },
    ],
    "NR-10-S": [
        {
            "id": "nr10s-q1",
            "prompt": "Para fins da NR 10, o Sistema Elétrico de Potência (SEP) compreende o conjunto de instalações e equipamentos destinados à:",
            "options": [
                "Iluminação interna de edifícios residenciais",
                "Geração, transmissão e distribuição de energia elétrica até a medição inclusive",
                "Acionamento de máquinas industriais de baixa tensão",
                "Fornecimento de EPI aos trabalhadores",
            ],
            "correct": 1,
        },
        {
            "id": "nr10s-q2",
            "prompt": "Conforme a classificação de tensão adotada no treinamento de SEP, considera-se alta tensão o valor:",
            "options": [
                "Inferior a 50 V em corrente alternada",
                "Superior a 1000 V em corrente alternada (ou 1500 V em corrente contínua)",
                "Igual a 220 V em corrente alternada",
                "Sempre inferior a 1000 V, qualquer que seja o sistema",
            ],
            "correct": 1,
        },
        {
            "id": "nr10s-q3",
            "prompt": "As técnicas de trabalho sob tensão no SEP incluem os métodos:",
            "options": [
                "À distância, ao contato e ao potencial",
                "Apenas o método ao potencial",
                "Somente o método à distância",
                "Trabalho exclusivamente em instalações desenergizadas",
            ],
            "correct": 0,
        },
        {
            "id": "nr10s-q4",
            "prompt": "A emissão de PES (Permissão de Entrada e Serviço) em instalações do SEP tem como objetivo:",
            "options": [
                "Substituir todos os procedimentos de segurança por uma autorização verbal",
                "Formalizar as condições e os controles necessários para a execução segura do serviço",
                "Dispensar a análise de risco prévia",
                "Permitir o trabalho sem EPI em situações de emergência",
            ],
            "correct": 1,
        },
        {
            "id": "nr10s-q5",
            "prompt": "Em trabalhos no SEP, a análise de risco deve ser realizada para:",
            "options": [
                "Apenas serviços de rotina sem exposição a risco elétrico",
                "Identificar os riscos e definir as medidas de controle antes da execução do serviço",
                "Substituir a necessidade de sinalização da área",
                "Dispensar o uso de procedimentos de emergência",
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


def grade_answers(
    course_code: str,
    answers: dict[str, int],
    *,
    minimum_score: float = MINIMUM_SCORE,
) -> tuple[int, int, float, bool]:
    """Grade a deterministic bank using the threshold pinned to the attempt.

    The default preserves the existing 60% demo policy. Regulatory attempts
    can supply the configured compliance threshold, and historical attempts
    remain auditable because their own ``minimum_score`` is used on submit.
    """
    if minimum_score < 0 or minimum_score > 100:
        raise ValueError("minimum_score must be between 0 and 100")
    bank = QUESTION_BANKS.get(course_code)
    if not bank:
        raise ValueError("Assessment is not configured for this course")
    correct = sum(1 for item in bank if answers.get(item["id"]) == item["correct"])
    total = len(bank)
    score = round((correct / total) * 100, 2) if total else 0.0
    return correct, total, score, score >= minimum_score
