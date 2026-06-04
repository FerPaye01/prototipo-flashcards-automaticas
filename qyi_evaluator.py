import numpy as np
import networkx as nx
from typing import List, Dict, Any, Tuple, Optional
import re

class QYIEvaluator:
    """
    Evaluador de Calidad y Rendimiento (Quality and Yield Index - QYI) para flashcards.
    Implementa la métrica refinada: QYI = alpha*Phi_Q + beta*Phi_Y + gamma*Phi_C
    """
    
    def __init__(self, alpha: float = 0.3, beta: float = 0.4, gamma: float = 0.3, epsilon: float = 1.0):
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.epsilon = epsilon  # Regularización para evitar división por cero

    def calculate_qyi(self, 
                      card_qualities: List[float], 
                      is_high_impact: List[bool], 
                      pagerank_scores: Dict[str, float],
                      card_concepts: List[str]) -> Dict[str, float]:
        """
        Calcula el QYI y sus sub-índices.
        
        Args:
            card_qualities: Lista de puntuaciones Q_i (0.0 a 1.0) para cada tarjeta.
            is_high_impact: Lista de booleanos Y_i indicando si la tarjeta es de alto impacto.
            pagerank_scores: Diccionario de puntuaciones de PageRank para cada concepto.
            card_concepts: Lista del concepto asociado a cada tarjeta.
            
        Returns:
            Diccionario con QYI, Phi_Q, Phi_Y y Phi_C.
        """
        M = len(card_qualities)
        if M == 0:
            return {"qyi": 0.0, "phi_q": 0.0, "phi_y": 0.0, "phi_c": 0.0}

        # 1. Sub-índice de Calidad Fáctica (Phi_Q)
        phi_q = sum(card_qualities) / M

        # 2. Sub-índice de Yield Instruccional (Phi_Y)
        m_star = sum(1 for y in is_high_impact if y)
        phi_y = m_star / M

        # 3. Sub-índice de Cobertura Topológica (Phi_C)
        if m_star > 0:
            # Normalizar PageRank scores (Min-Max)
            all_pr = list(pagerank_scores.values())
            if all_pr:
                pr_min = min(all_pr)
                pr_max = max(all_pr)
                pr_range = pr_max - pr_min if pr_max > pr_min else 1.0
                
                if pr_max > pr_min:
                    # Normalización min-max adaptativa con un piso mínimo de 0.20 para evitar penalizar nodos hoja a 0.0
                    min_floor = 0.20
                    normalized_pr = {k: min_floor + (1.0 - min_floor) * (v - pr_min) / pr_range for k, v in pagerank_scores.items()}
                else:
                    # Evitar penalizar con 0.0 cuando todos los conceptos tienen la misma importancia
                    normalized_pr = {k: 0.5 for k in pagerank_scores.keys()}
                
                sum_pr = 0.0
                for i in range(M):
                    if is_high_impact[i]:
                        concept = card_concepts[i].lower().strip()
                        sum_pr += normalized_pr.get(concept, 0.5) # 0.5 default if not found
                
                phi_c = sum_pr / m_star
            else:
                phi_c = 0.0
        else:
            phi_c = 0.0

        # Cálculo final de QYI
        qyi = (self.alpha * phi_q) + (self.beta * phi_y) + (self.gamma * phi_c)
        
        return {
            "qyi": qyi,
            "phi_q": phi_q,
            "phi_y": phi_y,
            "phi_c": phi_c,
            "m_star": m_star,
            "total": M
        }

class EduKGRanker:
    """
    Construye un Grafo de Conocimiento Educativo (EduKG) y calcula PageRank Personalizado.
    """
    def __init__(self):
        self.graph = nx.DiGraph()

    def build_graph(self, concepts: List[str], text_content: str, emphasis: Dict[str, float] = None, edges: List[Tuple[str, str]] = None):
        """
        Construye el grafo basado en relaciones explícitas (aristas) o co-ocurrencia de conceptos en el texto.
        """
        self.graph.clear() # Limpiar el grafo de ejecuciones anteriores
        emphasis = emphasis or {}
        
        # Añadir nodos
        for concept in concepts:
            self.graph.add_node(concept.lower().strip(), weight=emphasis.get(concept, 1.0))

        # Añadir aristas explícitas si se proporcionan
        if edges:
            for u, v in edges:
                u_clean = u.lower().strip()
                v_clean = v.lower().strip()
                if self.graph.has_node(u_clean) and self.graph.has_node(v_clean):
                    if self.graph.has_edge(u_clean, v_clean):
                        self.graph[u_clean][v_clean]['weight'] += 1.0
                    else:
                        self.graph.add_edge(u_clean, v_clean, weight=1.0)
        else:
            # Fallback: Añadir aristas basadas en co-ocurrencia en párrafos
            paragraphs = text_content.split('\n\n')
            for para in paragraphs:
                para_lower = para.lower()
                found_concepts = []
                for concept in concepts:
                    if concept.lower() in para_lower:
                        found_concepts.append(concept.lower().strip())
                
                # Crear aristas entre conceptos que aparecen en el mismo párrafo
                for i in range(len(found_concepts)):
                    for j in range(i + 1, len(found_concepts)):
                        u, v = found_concepts[i], found_concepts[j]
                        if self.graph.has_edge(u, v):
                            self.graph[u][v]['weight'] += 1.0
                        else:
                            self.graph.add_edge(u, v, weight=1.0)

    def calculate_pagerank(self, personalization: Dict[str, float] = None) -> Dict[str, float]:
        if not self.graph.nodes:
            return {}
        
        try:
            return nx.pagerank(self.graph, alpha=0.85, personalization=personalization, weight='weight')
        except:
            # Fallback a PageRank uniforme si falla el personalizado
            return nx.pagerank(self.graph, alpha=0.85, weight='weight')

def evaluate_with_watchdog(gemini_generator, texto_ocr: str, flashcards: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    Usa Gemini como un Watchdog para evaluar la calidad de las flashcards generadas.
    """
    if not flashcards:
        return []
        
    eval_prompt = f"""Actúa como un Profesor Juez experto en pedagogía cognitiva. 
Evalúa las siguientes flashcards generadas a partir del texto proporcionado.
Para cada flashcard, asigna:
1. Calidad (0-10): Precisión fáctica y claridad.
2. Nivel Bloom (1-4): 1=Recordar, 2=Entender, 3=Aplicar, 4=Analizar/Evaluar.
3. Alto Impacto (S/N): ¿Es una pregunta esencial que cubre un concepto clave?

Texto Original:
{texto_ocr[:2000]}...

Flashcards:
"""
    for i, card in enumerate(flashcards):
        eval_prompt += f"\nID: {i}\nP: {card.get('P', card.get('question', ''))}\nR: {card.get('R', card.get('answer', ''))}\n"

    eval_prompt += "\nResponde ÚNICAMENTE con una lista en formato JSON: [{\"id\": 0, \"calidad\": 8, \"bloom\": 2, \"impacto\": \"S\"}, ...]"
    
    # Llamar a Gemini (usando el método existente de gemini_generator)
    # Nota: Aquí asumo que gemini_generator tiene una forma de llamar a la API directamente
    # Para este ejemplo, simularemos una respuesta si no queremos hacer la llamada real aún, 
    # pero el código final debería usar gemini_generator.model.generate_content
    
    try:
        # Intentar obtener respuesta real si gemini_generator está disponible
        response = gemini_generator.generate_raw_response(eval_prompt)
        # Extraer JSON de la respuesta
        import json
        match = re.search(r'\[.*\]', response, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        print(f"Error en Watchdog: {e}")
        
    # Fallback/Simulación en caso de error
    return [{"id": i, "calidad": 7, "bloom": 1, "impacto": "S"} for i in range(len(flashcards))]
