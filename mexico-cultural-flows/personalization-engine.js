/**
 * AI Personalization Engine for Mexico Cultural Flows
 * Production-ready JavaScript (~700 lines)
 * Features: 10 Routes, 5-Question Quiz, Cosine Similarity Matching, Profile System
 */

// ═══════════════════════════════════════════════════════
// PART 1: 10 CULTURAL ROUTES
// ═══════════════════════════════════════════════════════

const CULTURAL_ROUTES = [
  {
    id: 'ruta-muralismo',
    name: 'Ruta del Muralismo Mexicano',
    description: 'Sigue los frescos gigante de Rivera, Orozco y Siqueiros a través de las walls más emblemáticas de México.',
    primaryCategory: 'arte',
    secondaryCategories: ['historia', 'arquitectura'],
    cities: ['cdmx', 'puebla', 'gdl'],
    highlights: [
      { name: 'Palacio Nacional, CDMX', desc: 'Los murales históricos de Diego Rivera narrando la conquista', duration_hours: 2.5 },
      { name: 'Bellas Artes, CDMX', desc: 'Orozco y Siqueiros en la sala principal', duration_hours: 1.5 },
      { name: 'Universidad PCEM, Puebla', desc: 'Murales contemporáneos en el claustro mayor', duration_hours: 1 },
      { name: 'Cordova Building, GDL', desc: 'Obras restauradas del mestizaje artístico', duration_hours: 1 }
    ],
    difficulty: 'medium',
    duration_days: 5,
    bestSeason: 'mar-abr',
    color: '#ec4899',
    icon: '🎨',
    tags: ['muralismo', 'diego-rivera', 'orozco', 'siqueiros', 'arte-publico'],
    prerequisites: ['interpretacion-historica', 'arte-moderno'],
    estimatedCost_usd: 350,
    accessibility: 'moderate',
    seasonalNotes: 'Mejor entre marzo y abril cuando la luz natural realza los colores'
  },
  {
    id: 'ruta-mariachi',
    name: 'Ruta del Mariachi y la Trova',
    description: 'Del Guadalajara tradicional al Veracruz jarocho, sigue los sonidos que conquistaron el mundo.',
    primaryCategory: 'musica',
    secondaryCategories: ['danza', 'historia'],
    cities: ['gdl', 'cdmx', 'ver'],
    highlights: [
      { name: 'Plaza de los Mariachis, GDL', desc: 'Espontáneo encuentro musical en la Glorieta', duration_hours: 2 },
      { name: 'Mercado de Sonidos, CDMX', desc: 'Los boleristas y trovadores del Zocalo', duration_hours: 1.5 },
      { name: ' Puerto de Veracruz', desc: 'Son jarocho en la jarana y la bamba', duration_hours: 2 },
      { name: 'Casa de la Trova, Xalapa', desc: 'Herencia afrocaribeña en la música', duration_hours: 1 }
    ],
    difficulty: 'easy',
    duration_days: 4,
    bestSeason: 'feb-mar',
    color: '#7c3aed',
    icon: '🎵',
    tags: ['mariachi', 'bolero', 'son-jarocho', 'trova', 'folclore'],
    prerequisites: ['apreciacion-musical'],
    estimatedCost_usd: 280,
    accessibility: 'easy',
    seasonalNotes: 'Festivales de primavera ofrecen mayor variedad de presentaciones'
  },
  {
    id: 'ruta-gastronomica',
    name: 'Ruta Gastronómica Ancestral',
    description: 'Moles, contrace, barbacoa y chocolate: un viaje por los sabores heredados de miles de años.',
    primaryCategory: 'gastro',
    secondaryCategories: ['historia', 'artesania'],
    cities: ['puebla', 'oax', 'cdmx'],
    highlights: [
      { name: 'Mercado 2 de Abril, Oaxaca', desc: 'Los siete moles y el mezcal artesanal', duration_hours: 3 },
      { name: 'San Juan Martopolis, Puebla', desc: 'Mole poblano tariareño y chiles en nogada', duration_hours: 2 },
      { name: ' Mercado de Coyoacán, CDMX', desc: 'Tacos de canasta y antojitos olvidados', duration_hours: 2 },
      { name: 'Chocolate Museum, CDMX', desc: 'HistÓrico del cacao y su preparacion ritual', duration_hours: 1.5 }
    ],
    difficulty: 'easy',
    duration_days: 4,
    bestSeason: 'nov-dic',
    color: '#ea580c',
    icon: '🍲',
    tags: ['mole', 'mezcal', 'cacao', 'tacos', 'antojitos'],
    prerequisites: ['sin-alergias-alimentarias'],
    estimatedCost_usd: 320,
    accessibility: 'easy',
    seasonalNotes: 'Día de Muertos_REALZA_la experien_ cuisine con moles especiales'
  },
  {
    id: 'ruta-danza-prehispanica',
    name: 'Ruta de la Danza Ancestral',
    description: 'Desde la Guelaguetza oaxaqueña hasta los Parachicos chiapanecos, revive las danzas est¹n precistas.',
    primaryCategory: 'danza',
    secondaryCategories: ['historia', 'artesania'],
    cities: ['oax', 'chis', 'yuc'],
    highlights: [
      { name: 'Auditorio Guelaguetza, Oaxaca', desc: 'La fiesta mayor de los Pueblos Indigenas', duration_hours: 3 },
      { name: 'Chiapa de Corzo, Chiapas', desc: 'Danza de los Parachicos en Enero', duration_hours: 2.5 },
      { name: 'Ceremonia Maya,Merida', desc: 'Jarana y danzas prehispanicas en el Colon', duration_hours: 2 },
      { name: 'San Cristobal', desc: 'Comparsas y danzas tzotziles en vivo', duration_hours: 1.5 }
    ],
    difficulty: 'medium',
    duration_days: 6,
    bestSeason: 'jul-ago',
    color: '#0891b2',
    icon: '💃',
    tags: ['guelaguetza', 'parachicos', 'jarana', 'danzas-rituales'],
    prerequisites: ['respeto-cultural', 'movimiento-fisico-moderado'],
    estimatedCost_usd: 380,
    accessibility: 'moderate',
    seasonalNotes: 'Calendario ritual estricto - Guelaguetza solo julio, Parachicos solo enero'
  },
  {
    id: 'ruta-artesania-color',
    name: 'Ruta de las Artesanias de Color',
    descRipcion: 'Barro negro, talavera, textiles y jade: las manos de México que transforman la tierra en arte.',
    primaryCategory: 'artesania',
    secondaryCategories: ['historia', 'arte'],
    cities: ['oax', 'puebla', 'chis', 'can'],
    highlights: [
      { name: 'San Bartolo Coyotepec,Oax', desc: 'Alfareria negra y sus MOStramientos', duration_hours: 2 },
      { name: 'Atelier Talavera,Puebla', desc: 'Taller donde se fabrica la ceramica Patrimonio', duration_hours: 2 },
      { name: 'Zinacantan,Chiapas', desc: 'Textiles tzotziles bordados a mano', duration_hours: 1.5 },
      { name: 'Tulum,Quintana Roo', desc: 'Jade y reliquias mayas recuperadas', duration_hours: 2 }
    ],
    difficulty: 'easy',
    duration_days: 5,
    bestSeason: 'oct-mar',
    color: '#16a34a',
    icon: '🏺',
    tags: ['barro-negro', 'talavera', 'textiles', 'jade', 'alfanderia'],
    prerequisites: ['interes-artesanal'],
    estimatedCost_usd: 300,
    accessibility: 'easy',
    seasonalNotes: 'Ferias de artesanias masivas en octubre-noviembre'
  },
  {
    id: 'ruta-impresionismo-mexicano',
    name: 'Ruta del Impresionismo Mexicano',
    description: 'Icaza, Voltan, Omeriled - los pintores que capturaron la luz de México al atardecer.',
    primaryCategory: 'arte',
    secondaryCategories: ['historia'],
    cities: ['cdmx', 'gdl', 'puebla'],
    highlights: [
      { name: 'Museo del Impresionismo, CDMX', desc: 'Colección permanente de la Escuela Nacional de Pintura', duration_hours: 2 },
      { name: 'Pinacoteca-Instituto Cultural, GDL', desc: 'Pintores jaliscienses del siglo XX', duration_hours: 1.5 },
      { name: 'Casa-Museo Lola Cabrera, Puebla', desc: 'Movimiento impresionista poblano', duration_hours: 1 }
    ],
    difficulty: 'easy',
    duration_days: 3,
    bestSeason: 'abr-may',
    color: '#f97316',
    icon: '🖼️',
    tags: ['impresionismo', 'pintura', 'elenco-mexicano', 'gota-de-luz'],
    prerequisites: ['apreciacion-artistica'],
    estimatedCost_usd: 200,
    accessibility: 'easy',
    seasonalNotes: 'Mejor luz durante las tardes de primavera para apreciación de obras'
  },
  {
    id: 'ruta-industrial-norte',
    name: 'Ruta Industrial del Norte',
    description: 'Monterrey, Tijuana y la frontera: zonas industriales que crearon una cultura única frente al desierto.',
    primaryCategory: 'historia',
    secondaryCategories: ['musica', 'gastro'],
    cities: ['mtry', 'tj', 'cdmx'],
    highlights: [
      { name: 'Puerto Maritimo, Monterrey', desc: 'Museo de Historia Mexicana y el Obelisco', duration_hours: 2 },
      { name: 'Cerveza Cervecería, MTY', desc: 'Industrialismo en su máxima expresion', duration_hours: 1.5 },
      { name: 'Centro Arte Tijuana, TJ', desc: 'La vanguardia artistica de la frontera', duration_hours: 1.5 },
      { name: 'Grutas Tolantongo, MTY', desc: 'Paraje natural de la Sierra Madre', duration_hours: 3 }
    ],
    difficulty: 'medium',
    duration_days: 4,
    bestSeason: 'oct-mar',
    color: '#6b7280',
    icon: '⚙️',
    tags: ['industrial', 'frontera', 'norteno', 'cuadrado'],
    prerequisites: ['interés-moderado-historia'],
    estimatedCost_usd: 340,
    accessibility: 'easy',
    seasonalNotes: 'Evitar julio-agosto (calor extremo en el norte)'
  },
  {
    id: 'ruta-yucatan-maya',
    name: 'Ruta del Mundo Maya',
    description: 'Chichén Itzá, Uxmal, Palenque y Tulum: las ciudades metropolitanas del imperio mesoamericano más grande.',
    primaryCategory: 'historia',
    secondaryCategories: ['arqueologia', 'artesania'],
    cities: ['yuc', 'can', 'chis'],
    highlights: [
      { name: 'Chichen-Itza,Yucatan', desc: 'La maravilla arquitectonica del El Castillo', duration_hours: 4 },
      { name: 'Uxmal, Yucatan', desc: 'Palacio del Gobernador y la Piramide del Adivino', duration_hours: 3 },
      { name: 'Palenque, Chiapas', desc: 'Templo de las Inscripciones de Pakal', duration_hours: 3 },
      { name: 'Tulum, Quintana Roo', desc: 'La ciudad amurallada frente al Caribe', duration_hours: 2 }
    ],
    difficulty: 'medium',
    duration_days: 7,
    bestSeason: 'nov-abr',
    color: '#eab308',
    icon: '🏛️',
    tags: ['mayas', 'chichen', 'uxmal', 'palenque', 'tulum', 'arqueología'],
    prerequisites: ['paciencia-peatonal', 'calor-alto-resistencia'],
    estimatedCost_usd: 500,
    accessibility: 'moderate',
    seasonalNotes: 'Temporada alta = masivos tour. Febrero-marzo tiene clima perfecto'
  },
  {
    id: 'ruta-afrocaribe',
    name: 'Ruta Afrocaribeña',
    description: 'Veracruz, Yucatán y la costa: las raíces africanas que dieron ritmo al son jarocho y la cultura caribeña.',
    primaryCategory: 'musica',
    secondaryCategories: ['danza', 'gastro', 'historia'],
    cities: ['ver', 'yuc', 'can'],
    highlights: [
      { name: 'Jarocho, Veracruz', desc: 'La Bamba y el son en sus origenes', duration_hours: 2 },
      { name: 'Carnaval de Veracruz', desc: 'El orgullo afrocaribeño en la manifests', duration_hours: 3 },
      { name: 'Isla de Mujeres', desc: 'Fusión caribeña en la gastronoma maya', duration_hours: 2 },
      { name: 'Danza del Caribe, Merida', desc: 'Tradición y fusion cultural', duration_hours: 1.5 }
    ],
    difficulty: 'easy',
    duration_days: 5,
    bestSeason: 'feb-mar',
    color: '#ec4899',
    icon: '🌴',
    tags: ['afro', 'son-jarocho', 'caribe', 'carnaval'],
    prerequisites: ['rutas-culturales', 'disfruta-paisajes'],
    estimatedCost_usd: 380,
    accessibility: 'easy',
    seasonalNotes: 'Carnaval de Veracruz Fija el mes de Febrero'
  },
  {
    id: 'ruta-colonial-barroco',
    name: 'Ruta del Barroco Novohispano',
    description: 'Catedrales, conventos y palacios donde el barroco español se fundió con lo indígena.',
    primaryCategory: 'arquitectura',
    secondaryCategories: ['arte', 'historia'],
    cities: ['puebla', 'cdmx', 'oax', 'gdl'],
    highlights: [
      { name: 'Catedral de Puebla', desc: 'Barroco mexihuitl con talavera en los muros', duration_hours: 2 },
      { name: 'San Francisco Acatepec, Puebla', desc: 'Templo cubierto completamente de talavera', duration_hours: 1.5 },
      { name: 'Santa Maria Tonantzintla', desc: 'El barroco más indigena de Mexico', duration_hours: 1.5 },
      { name: 'Templo de Santo Domingo, Oax', desc: 'El retablo dorado más espectacular', duration_hours: 2 }
    ],
    difficulty: 'easy',
    duration_days: 4,
    bestSeason: 'mar-may',
    color: '#8b5cf6',
    icon: '⛪',
    tags: ['barroco', 'colonial', 'arquitectura', 'conventos', 'talavera'],
    prerequisites: ['angustiacion-arquitectura'],
    estimatedCost_usd: 280,
    accessibility: 'easy',
    seasonalNotes: 'Semana Santa atrae mayor cantidad de eventos religiosos y culturales'
  }
];

// Category weight mapping: each answer contributes to 15 categories
const CATEGORY_WEIGHTS = {
  arte: 1, musica: 2, gastro: 3, danza: 4, artesania: 5,
  historia: 6, arquitectura: 7, arqueologia: 8,
  folklore: 9, espiritualidad: 10, naturaleza: 11,
  vanguardia: 12, comunidad: 13, aventura: 14, artisanal: 15
};

//════════════════════════════════════════════════════════
// PART 2: 5-QUESTION QUIZ
//════════════════════════════════════════════════════════

const QUIZ_QUESTIONS = [
  {
    id: 'q1_art_form',
    question: '¿Qué forma de expresión artística te atrae más?',
    category: 'art_form',
    options: [
      { text: 'Pintura y murales de gran escala', weights: { arte: 30, historia: 15, arquitectura: 10 } },
      { text: 'Música en vivo y presentaciones musicales', weights: { musica: 35, danza: 20, folklore: 15 } },
      { text: 'Gastronomía y experiencias culinarias', weights: { gastro: 40, artesania: 15, comunida: 10 } },
      { text: 'Danza y rituales en movimiento', weights: { danza: 35, espiritualidad: 20, folklore: 15 } },
      { text: 'Artesanía y objetos hechos a mano', weights: { artesania: 35, historia: 15, architectural: 10 } }
    ]
  },
  {
    id: 'q2_historical_era',
    question: '¿Qué época histórica te genera más curiosidad?',
    category: 'historical_era',
    options: [
      { text: 'Época prehispánica y civilizaciones antiguas', weights: { historia: 30, arqueologia: 25, espiritualidad: 15 } },
      { text: 'Época colonial y el barroco novohispano', weights: { arquitectura: 30, arte: 20, historia: 20 } },
      { text: 'Siglo XIX y la Independencia', weights: { historia: 35, arte: 15, vanguardia: 10 } },
      { text: 'Siglo XX y el México moderno', weights: { arte: 30, vanguardia: 25, historia: 15 } },
      { text: 'México contemporáneo y vanguardia', weights: { vanguardia: 35, arte: 20, comunidad: 15 } }
    ]
  },
  {
    id: 'q3_learning_style',
    question: '¿Cómo prefieres aprender sobre cultura?',
    category: 'learning_style',
    options: [
      { text: 'Observando y contemplando en museos', weights: { arte: 25, historia: 20, arquitectura: 15 } },
      { text: 'Escuchando y participando en eventos', weights: { musica: 30, danza: 25, folklore: 15 } },
      { text: 'Probando y experimentando sabores', weights: { gastro: 35, comunidad: 15, artisanal: 10 } },
      { text: 'Leyendo placas y guiándome por historia', weights: { historia: 35, arqueologia: 20, arquitectura: 10 } },
      { text: 'Creando con mis propias manos', weights: { artesania: 35, artistico: 20, folklore: 10 } }
    ]
  },
  {
    id: 'q4_travel_pace',
    question: '¿Cuál es tu ritmo de viaje ideal?',
    category: 'travel_pace',
    options: [
      { text: 'Rápido - 5-7 ciudades en pocos días', weights: { aventura: 30, historia: 20, vanguardia: 15 } },
      { text: 'Moderado - 3-4 ciudades con tiempo', weights: { comunidad: 25, gastro: 20, artesania: 15 } },
      { text: 'Relajado - concentrarme en 1-2 lugares', weights: { espiritualidad: 25, folklore: 20, naturaleza: 15 } },
      { text: 'Inmersivo - vivir como local en un sitio', weights: { comunidad: 30, artesania: 25, gastro: 15 } },
      { text: 'Flexible - sin horarios estrictos', weights: { aventura: 25, naturaleza: 20, vanguardia: 15 } }
    ]
  },
  {
    id: 'q5_group_type',
    question: '¿En qué tipo de grupo viajas?',
    category: 'group_type',
    options: [
      { text: 'Solo, buscando experiencias personales', weights: { espiritualidad: 25, arte: 20, aventura: 15 } },
      { text: 'En pareja, buscando romanticismo', weights: { gastro: 25, danza: 20, naturaleza: 15 } },
      { text: 'Amigos, buscando diversión en grupo', weights: { musica: 30, gastro: 20, vanguardia: 15 } },
      { text: 'Familia con niños', weights: { artesania: 25, folklore: 20, comunidad: 15 } },
      { text: 'Grupa educativo/histórico', weights: { historia: 30, arqueologia: 25, arquitectura: 15 } }
    ]
  }
];

//════════════════════════════════════════════════════════
// PART 3: ALGORITHMS (COSINE SIMILARITY)
//════════════════════════════════════════════════════════

/**
 * Calculates cosine similarity between two vectors
 * Formula: cos(θ) = (A · B) / (|A| × |B|)
 * @param {number[]} vec1 - First preference vector (15 dimensions)
 * @param {number[]} vec2 - Second vector (route profile)
 * @returns {number} Similarity score between -1 and 1
 */
function calculateCosineSimilarity(vec1, vec2) {
  if (!Array.isArray(vec1) || !Array.isArray(vec2)) {
    console.error('Both inputs must be arrays:', { vec1, vec2 });
    return 0;
  }

  if (vec1.length !== vec2.length) {
    console.error('Vector length mismatch:', { vec1Length: vec1.length, vec2Length: vec2.length });
    return 0;
  }

  // If vectors are too short, pad with zeros
  const length = 15; // Our category dimension
  const v1 = [...vec1].concat(Array(Math.max(0, length - vec1.length)).fill(0));
  const v2 = [...vec2].concat(Array(Math.max(0, length - vec2.length)).fill(0));

  let dotProduct = 0;
  let magnitude1 = 0;
  let magnitude2 = 0;

  for (let i = 0; i < length; i++) {
    dotProduct += v1[i] * v2[i];
    magnitude1 += v1[i] * v1[i];
    magnitude2 += v2[i] * v2[i];
  }

  magnitude1 = Math.sqrt(magnitude1);
  magnitude2 = Math.sqrt(magnitude2);

  if (magnitude1 === 0 || magnitude2 === 0) {
    return 0; // Avoid division by zero
  }

  return dotProduct / (magnitude1 * magnitude2);
}

/**
 *Converts a route into a 15-dimension preference vector
 * @param {object} route - Cultural route object
 * @returns {number[]} 15-element array of category scores (0-100)
 */
function routeToPreferenceVector(route) {
  const vector = new Array(15).fill(0);

  // Primary category: high weight
  const primaryIdx = CATEGORY_WEIGHTS[route.primaryCategory];
  if (primaryIdx) {
    vector[primaryIdx - 1] = 100; // Full weight for primary
  }

  // Secondary categories: medium weight
  if (route.secondaryCategories && Array.isArray(route.secondaryCategories)) {
    route.secondaryCategories.forEach(cat => {
      const idx = CATEGORY_WEIGHTS[cat];
      if (idx) {
        vector[idx - 1] = 60; // Secondary gets 60% weight
      }
    });
  }

  // Adjust based on difficulty
  const difficultyBonus = {
    'easy': { naturaleza: 10, aventura: 5 },
    'medium': { adventure: 15, desafio: 10 },
    'hard': { aventura: 25, espiritu: 10 }
  };

  if (difficultyBonus[route.difficulty]) {
    Object.entries(difficultyBonus[route.difficulty]).forEach(([cat, bonus]) => {
      const idx = CATEGORY_WEIGHTS[cat];
      if (idx) {
        vector[idx - 1] = Math.min(100, vector[idx - 1] + bonus);
      }
    });
  }

  // Tags influence additional dimensions
  if (route.tags && Array.isArray(route.tags)) {
    route.tags.forEach(tag => {
      if (tag.includes('rural') || tag.includes('natural')) {
        vector[10] = Math.min(100, vector[10] + 15); // naturaleza
      }
      if (tag.includes('vanguardia') || tag.includes('moderno')) {
        vector[11] = Math.min(100, vector[11] + 20); // vanguardia
      }
      if (tag.includes('ritual') || tag.includes('festejo')) {
        vector[9] = Math.min(100, vector[9] + 25); // espiritualidad
      }
      if (tag.includes('comunitario') || tag.includes('pueblo')) {
        vector[12] = Math.min(100, vector[12] + 20); // comunidad
      }
    });
  }

  return vector;
}

/**
 * Top to 15-dimension vector based on quiz answers
 * @param {object[]} answers - Array of {questionId, optionIndex} objects
 * @returns {number[]} 15-element weight vector
 */
function calculateUserPreferences(answers) {
  const vector = new Array(15).fill(0);

  answers.forEach(answer => {
    const question = QUIZ_QUESTIONS.find(q => q.id === answer.questionId);
    if (!question) {
      console.warn('Question not found:', answer.questionId);
      return;
    }

    const option = question.options[answer.optionIndex];
    if (!option) {
      console.warn('Option not found:', answer.optionIndex);
      return;
    }

    // Add weights from selected option
    Object.entries(option.weights).forEach(([category, weight]) => {
      const idx = CATEGORY_WEIGHTS[category];
      if (idx) {
        vector[idx - 1] += weight;
      }
    });
  });

  // Normalize to 0-100 range
  const maxCategory = Math.max(...vector);
  if (maxCategory > 0) {
    vector.forEach((val, i) => {
      vector[i] = Math.round((val / maxCategory) * 100);
    });
  }

  return vector;
}

/**
 * Matches routes to user preferences and returns ranked list
 * @param {number[]} userWeights - 15-element preference vector
 * @param {number} topN - Number of top matches to return
 * @returns {object[]} Ranked array of {route, score, matchReason}
 */
function matchRoutesToPreferences(userWeights, topN = 3) {
  const matches = CULTURAL_ROUTES.map(route => {
    const routeVector = routeToPreferenceVector(route);
    const similarity = calculateCosineSimilarity(userWeights, routeVector);
    const score = Number((similarity * 100).toFixed(1)); // 0-100 scale

    // Generate match reason
    const matchReason = generateMatchReason(route, similarity, userWeights, routeVector);

    return {
      route,
      score,
      similarity,
      matchReason,
      routeVector
    };
  });

  // Sort by score (descending)
  matches.sort((a, b) => b.score - a.score);

  return matches.slice(0, topN);
}

/**
 * Generates a human-readable match reason
 */
function generateMatchReason(route, similarity, userWeights, routeVector) {
  const reasons = [];

  if (similarity > 0.8) {
    reasons.push('¡Alta coincidencia con tus intereses!');
  } else if (similarity > 0.6) {
    reasons.push('Se alinea muy bien con tus preferencias.');
  } else if (similarity > 0.4) {
    reasons.push('Coincide moderadamente con tus gustos.');
  } else {
    reasons.push('Una exploración fuera de tu zona de confort.');
  }

  // Highlight top matching categories
  const matchedCats = [];
  Object.entries(CATEGORY_WEIGHTS).forEach(([cat, idx]) => {
    const userWeight = userWeights[idx - 1] || 0;
    const routeWeight = routeVector[idx - 1] || 0;
    if (userWeight > 50 && routeWeight > 50) {
      matchedCats.push(cat);
    }
  });

  if (matchedCats.length > 0) {
    reasons.push(`Perfecto para ${matchedCats.slice(0, 2).join(' y ')}.`);
  }

  if (route.difficulty === 'easy') {
    reasons.push('Poco exigente físicamente.');
  } else if (route.difficulty === 'hard') {
    reasons.push('Para exploradores resistentes.');
  }

  return reasons.join(' ');
}

/**
 * Generates a "surprising" alternative route (diversification)
 * Finds routes with moderate similarity (0.3-0.5) that offer contrast
 * @param {string} baseRouteId - The currently selected route ID
 * @param {number[]} userWeights - User preference vector
 * @returns {object|null} Surprising route or null if none found
 */
function generateSurprisingRoute(baseRouteId, userWeights) {
  const baseRoute = CULTURAL_ROUTES.find(r => r.id === baseRouteId);
  if (!baseRoute) return null;

  const baseVector = routeToPreferenceVector(baseRoute);

  const surprises = CULTURAL_ROUTES
    .filter(r => r.id !== baseRouteId)
    .map(route => {
      const routeVector = routeToPreferenceVector(route);
      const similarity = calculateCosineSimilarity(baseVector, routeVector);
      const userSimilarity = calculateCosineSimilarity(userWeights, routeVector);
      const score = Number((userSimilarity * 100).toFixed(1));

      return {
        route,
        similarity,
        userSimilarity,
        score
      };
    })
    .filter(r => r.similarity >= 0.3 && r.similarity <= 0.6) // Moderate contrast
    .sort((a, b) => b.userSimilarity - a.userSimilarity);

  return surprises.length > 0 ? surprises[0].route : null;
}

/**
 * Creates a "wild card" recommendation (completely different category)
 * @param {string} baseRouteId - Currently selected route ID
 * @returns {object|null} Wild card route or null
 */
function generateWildCardRoute(baseRouteId) {
  const baseRoute = CULTURAL_ROUTES.find(r => r.id === baseRouteId);
  if (!baseRoute) return null;

  // Find route with different primary category
  const wildCards = CULTURAL_ROUTES
    .filter(r => r.id !== baseRouteId && r.primaryCategory !== baseRoute.primaryCategory)
    .sort((a, b) => {
      const categoryDiffA = a.primaryCategory === baseRoute.primaryCategory ? 0 : 1;
      const categoryDiffB = b.primaryCategory === baseRoute.primaryCategory ? 0 : 1;
      return categoryDiffA - categoryDiffB || a.duration_days - b.duration_days;
    });

  return wildCards.length > 0 ? wildCards[0] : null;
}

//════════════════════════════════════════════════════════
// PART 4: USER PROFILE SYSTEM
//════════════════════════════════════════════════════════

const PROFILE_STORAGE_KEY = 'mexicoCulturalFlows_userProfile_v1';

/**
 * User profile interface:
 * {
 *   id: string (UUID),
 *   name: string,
 *   quizCompleted: boolean,
 *   lastQuizAnswers: {questionId, optionIndex}[],
 *   preferenceVector: number[],
 *   favoriteRoutes: string[],
 *   viewHistory: {routeId, timestamp, duration_seconds}[],
 *   createdAt: number (timestamp),
 *   lastActive: number (timestamp),
 *   settings: {
 *     notifications: boolean,
 *     sharingEnabled: boolean,
 *     language: 'es' | 'en'
 *   }
 * }
 */

class UserProfileManager {
  constructor() {
    this.currentProfile = null;
    this.listeners = [];
  }

  /**
   * Load profile from localStorage
   * @returns {object|null} Loaded profile or null
   */
  loadProfile() {
    try {
      const stored = localStorage.getItem(PROFILE_STORAGE_KEY);
      if (stored) {
        this.currentProfile = JSON.parse(stored);
        this.notifyListeners('profile:loaded', this.currentProfile);
        return this.currentProfile;
      }
    } catch (error) {
      console.error('Error loading profile:', error);
    }
    return null;
  }

  /**
   * Create a new profile
   * @param {string} name - User's name
   * @param {object} settings - Optional initial settings
   * @returns {object} New profile
   */
  createProfile(name, settings = {}) {
    const now = Date.now();
    this.currentProfile = {
      id: this._generateUUID(),
      name: name || 'Explorador',
      quizCompleted: false,
      lastQuizAnswers: [],
      preferenceVector: new Array(15).fill(0),
      favoriteRoutes: [],
      viewHistory: [],
      createdAt: now,
      lastActive: now,
      settings: {
        notifications: true,
        sharingEnabled: true,
        language: 'es',
        ...settings
      }
    };
    this.saveProfile();
    this.notifyListeners('profile:created', this.currentProfile);
    return this.currentProfile;
  }

  /**
   * Save current profile to localStorage
   * @returns {boolean} Success
   */
  saveProfile() {
    if (!this.currentProfile) {
      console.warn('Cannot save: no profile loaded');
      return false;
    }
    try {
      this.currentProfile.lastActive = Date.now();
      localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(this.currentProfile));
      this.notifyListeners('profile:saved', this.currentProfile);
      return true;
    } catch (error) {
      console.error('Error saving profile:', error);
      return false;
    }
  }

  /**
   * Update preferences from quiz answers
   * @param {object[]} answers - Quiz answers
   * @returns {object} Updated profile
   */
  completeQuiz(answers) {
    if (!this.currentProfile) {
      this._ensureProfile();
    }

    const preferenceVector = calculateUserPreferences(answers);

    this.currentProfile.quizCompleted = true;
    this.currentProfile.lastQuizAnswers = answers;
    this.currentProfile.preferenceVector = preferenceVector;
    this.currentProfile.recommendations = matchRoutesToPreferences(preferenceVector, 5);

    this.saveProfile();
    this.notifyListeners('profile:quizComplete', this.currentProfile);
    return this.currentProfile;
  }

  /**
   * Record a view to history
   * @param {string} routeId - Route ID viewed
   * @param {number} duration_seconds - View duration
   */
  recordView(routeId, durationSeconds = 30) {
    if (!this.currentProfile) {
      this._ensureProfile();
    }

    this.currentProfile.viewHistory.push({
      routeId,
      timestamp: Date.now(),
      duration_seconds: durationSeconds
    });

    // Keep only last 50 views
    if (this.currentProfile.viewHistory.length > 50) {
      this.currentProfile.viewHistory = this.currentProfile.viewHistory.slice(-50);
    }

    this.saveProfile();
    this.notifyListeners('profile:viewRecorded', { routeId, durationSeconds });
  }

  /**
   * Toggle favorite status for a route
   * @param {string} routeId - Route ID
   * @returns {boolean} New favorite status
   */
  toggleFavorite(routeId) {
    if (!this.currentProfile) {
      this._ensureProfile();
    }

    const idx = this.currentProfile.favoriteRoutes.indexOf(routeId);
    if (idx >= 0) {
      this.currentProfile.favoriteRoutes.splice(idx, 1);
      this.notifyListeners('profile:favoriteRemoved', routeId);
    } else {
      this.currentProfile.favoriteRoutes.push(routeId);
      this.notifyListeners('profile:favoriteAdded', routeId);
    }

    this.saveProfile();
    return idx < 0; // Return true if now favorited
  }

  /**
   * Update profile settings
   * @param {object} newSettings - Settings to merge
   * @returns {object} Updated profile
   */
  updateSettings(newSettings) {
    if (!this.currentProfile) {
      this._ensureProfile();
    }

    this.currentProfile.settings = {
      ...this.currentProfile.settings,
      ...newSettings
    };
    this.saveProfile();
    this.notifyListeners('profile:settingsUpdated', this.currentProfile.settings);
    return this.currentProfile;
  }

  /**
   * Get personalized recommendations
   * @returns {object[]} Ranked recommendations
   */
  getRecommendations() {
    if (!this.currentProfile) return [];

    if (this.currentProfile.recommendations) {
      // Return cached recommendations
      return this.currentProfile.recommendations;
    }

    // Generate fresh recommendations
    if (this.currentProfile.preferenceVector.some(v => v > 0)) {
      const recs = matchRoutesToPreferences(this.currentProfile.preferenceVector, 5);
      this.currentProfile.recommendations = recs;
      this.saveProfile();
      return recs;
    }

    return [];
  }

  /**
   * Get view statistics
   * @returns {object} View stats
   */
  getViewStats() {
    if (!this.currentProfile) return { totalViews: 0, totalMinutes: 0, uniqueRoutes: 0 };

    const views = this.currentProfile.viewHistory;
    return {
      totalViews: views.length,
      totalMinutes: Math.round(views.reduce((sum, v) => sum + v.duration_seconds, 0) / 60),
      uniqueRoutes: new Set(views.map(v => v.routeId)).size,
      favoriteRoutes: this.currentProfile.favoriteRoutes.length
    };
  }

  /**
   * Register listener for profile events
   * @param {function} callback - Event handler
   */
  subscribe(callback) {
    this.listeners.push(callback);
  }

  _ensureProfile() {
    if (!this.currentProfile) {
      this.createProfile('Explorador');
    }
  }

  _generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }

  notifyListeners(event, data) {
    this.listeners.forEach(cb => {
      try {
        cb(event, data);
      } catch (error) {
        console.error('Listener error:', error);
      }
    });
  }
}

//════════════════════════════════════════════════════════
// QUIZ COMPONENT (State Machine)
//════════════════════════════════════════════════════════

class QuizEngine {
  constructor(onComplete) {
    this.onStartCallback = onComplete;
    this.currentQuestion = 0;
    this.answers = [];
    this.hasStarted = false;
  }

  getProgress() {
    return {
      current: this.currentQuestion,
      total: QUIZ_QUESTIONS.length,
      percent: (this.currentQuestion / QUIZ_QUESTIONS.length) * 100
    };
  }

  getCurrentQuestion() {
    return QUIZ_QUESTIONS[this.currentQuestion];
  }

  selectOption(optionIndex) {
    const question = QUIZ_QUESTIONS[this.currentQuestion];
    if (!question || optionIndex < 0 || optionIndex >= question.options.length) {
      return false;
    }

    // Store answer
    this.answers.push({
      questionId: question.id,
      optionIndex,
      option: question.options[optionIndex],
      timestamp: Date.now()
    });

    // Move to next question or complete
    if (this.currentQuestion < QUIZ_QUESTIONS.length - 1) {
      this.currentQuestion++;
      return 'next';
    } else {
      this.hasStarted = true;
      this.onCompleteCallback?.(this.answers);
      return 'complete';
    }
  }

  skip() {
    if (this.currentQuestion < QUIZ_QUESTIONS.length - 1) {
      this.currentQuestion++;
      return 'next';
    }
    return 'complete';
  }

  restart() {
    this.currentQuestion = 0;
    this.answers = [];
    this.hasStarted = false;
  }
}

//════════════════════════════════════════════════════════
// EXPORTS (for module systems)
//════════════════════════════════════════════════════════

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    CULTURAL_ROUTES,
    QUIZ_QUESTIONS,
    CATEGORY_WEIGHTS,
    calculateCosineSimilarity,
    routeToPreferenceVector,
    calculateUserPreferences,
    matchRoutesToPreferences,
    generateSurprisingRoute,
    generateWildCardRoute,
    UserProfileManager,
    QuizEngine
  };
}