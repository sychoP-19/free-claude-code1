export interface FoodItem {
  id: string;
  name: string;
  category: 'food' | 'drink';
  servingSize: string;
  servingGrams: number;
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
  fiber: number;
  waterMl: number;
}

export const FOOD_DB: FoodItem[] = [
  // Proteins
  { id: 'chicken-breast', name: 'Chicken Breast (grilled)', category: 'food', servingSize: '100g', servingGrams: 100, calories: 165, protein: 31, carbs: 0, fat: 3.6, fiber: 0, waterMl: 65 },
  { id: 'eggs', name: 'Eggs (whole)', category: 'food', servingSize: '2 large', servingGrams: 100, calories: 143, protein: 12.6, carbs: 0.7, fat: 9.5, fiber: 0, waterMl: 75 },
  { id: 'salmon', name: 'Salmon (baked)', category: 'food', servingSize: '100g', servingGrams: 100, calories: 208, protein: 20, carbs: 0, fat: 13, fiber: 0, waterMl: 62 },
  { id: 'ground-beef', name: 'Ground Beef (lean)', category: 'food', servingSize: '100g', servingGrams: 100, calories: 250, protein: 26, carbs: 0, fat: 15, fiber: 0, waterMl: 58 },
  { id: 'tuna', name: 'Canned Tuna', category: 'food', servingSize: '1 can (85g)', servingGrams: 85, calories: 100, protein: 22, carbs: 0, fat: 0.5, fiber: 0, waterMl: 55 },
  { id: 'turkey', name: 'Turkey Breast', category: 'food', servingSize: '100g', servingGrams: 100, calories: 135, protein: 30, carbs: 0, fat: 1, fiber: 0, waterMl: 70 },
  { id: 'tofu', name: 'Tofu (firm)', category: 'food', servingSize: '100g', servingGrams: 100, calories: 144, protein: 17, carbs: 3, fat: 8, fiber: 2, waterMl: 70 },
  { id: 'shrimp', name: 'Shrimp (cooked)', category: 'food', servingSize: '100g', servingGrams: 100, calories: 99, protein: 24, carbs: 0.2, fat: 0.3, fiber: 0, waterMl: 75 },
  { id: 'beans-black', name: 'Black Beans', category: 'food', servingSize: '1 cup', servingGrams: 172, calories: 227, protein: 15, carbs: 41, fat: 0.9, fiber: 15, waterMl: 120 },
  { id: 'lentils', name: 'Lentils (cooked)', category: 'food', servingSize: '1 cup', servingGrams: 198, calories: 230, protein: 18, carbs: 40, fat: 0.8, fiber: 16, waterMl: 130 },
  // Grains & Carbs
  { id: 'rice-white', name: 'White Rice (cooked)', category: 'food', servingSize: '1 cup', servingGrams: 158, calories: 206, protein: 4.3, carbs: 45, fat: 0.4, fiber: 0.6, waterMl: 110 },
  { id: 'rice-brown', name: 'Brown Rice (cooked)', category: 'food', servingSize: '1 cup', servingGrams: 195, calories: 216, protein: 5, carbs: 45, fat: 1.8, fiber: 3.5, waterMl: 110 },
  { id: 'potato', name: 'Potato (baked)', category: 'food', servingSize: '1 medium', servingGrams: 173, calories: 161, protein: 4.3, carbs: 37, fat: 0.2, fiber: 3.8, waterMl: 120 },
  { id: 'sweet-potato', name: 'Sweet Potato (baked)', category: 'food', servingSize: '1 medium', servingGrams: 114, calories: 103, protein: 2.3, carbs: 24, fat: 0.1, fiber: 3.8, waterMl: 80 },
  { id: 'oatmeal', name: 'Oatmeal (cooked)', category: 'food', servingSize: '1 cup', servingGrams: 234, calories: 154, protein: 6, carbs: 27, fat: 2.6, fiber: 4, waterMl: 170 },
  { id: 'bread-wheat', name: 'Whole Wheat Bread', category: 'food', servingSize: '1 slice', servingGrams: 28, calories: 69, protein: 3.6, carbs: 12, fat: 1.1, fiber: 1.9, waterMl: 8 },
  { id: 'bread-white', name: 'White Bread', category: 'food', servingSize: '1 slice', servingGrams: 30, calories: 79, protein: 2.7, carbs: 15, fat: 1, fiber: 0.6, waterMl: 8 },
  { id: 'pasta', name: 'Pasta (cooked)', category: 'food', servingSize: '1 cup', servingGrams: 140, calories: 220, protein: 8, carbs: 43, fat: 1.3, fiber: 2.5, waterMl: 90 },
  { id: 'tortilla', name: 'Flour Tortilla', category: 'food', servingSize: '1 medium', servingGrams: 45, calories: 146, protein: 3.7, carbs: 24, fat: 3.6, fiber: 1.4, waterMl: 12 },
  { id: 'corn-tortilla', name: 'Corn Tortilla', category: 'food', servingSize: '1 medium', servingGrams: 26, calories: 52, protein: 1.4, carbs: 11, fat: 0.7, fiber: 1.5, waterMl: 10 },
  // Fruits
  { id: 'banana', name: 'Banana', category: 'food', servingSize: '1 medium', servingGrams: 118, calories: 105, protein: 1.3, carbs: 27, fat: 0.4, fiber: 3.1, waterMl: 88 },
  { id: 'apple', name: 'Apple', category: 'food', servingSize: '1 medium', servingGrams: 182, calories: 95, protein: 0.5, carbs: 25, fat: 0.3, fiber: 4.4, waterMl: 140 },
  { id: 'orange', name: 'Orange', category: 'food', servingSize: '1 medium', servingGrams: 131, calories: 62, protein: 1.2, carbs: 15, fat: 0.2, fiber: 3.1, waterMl: 110 },
  { id: 'strawberries', name: 'Strawberries', category: 'food', servingSize: '1 cup', servingGrams: 152, calories: 49, protein: 1, carbs: 12, fat: 0.5, fiber: 3, waterMl: 132 },
  { id: 'avocado', name: 'Avocado', category: 'food', servingSize: '1/2 medium', servingGrams: 68, calories: 114, protein: 1.3, carbs: 6, fat: 10.5, fiber: 4.6, waterMl: 45 },
  { id: 'mango', name: 'Mango', category: 'food', servingSize: '1 cup', servingGrams: 165, calories: 99, protein: 1.4, carbs: 25, fat: 0.6, fiber: 2.6, waterMl: 130 },
  // Vegetables
  { id: 'broccoli', name: 'Broccoli (steamed)', category: 'food', servingSize: '1 cup', servingGrams: 156, calories: 55, protein: 3.7, carbs: 11, fat: 0.6, fiber: 5.1, waterMl: 130 },
  { id: 'spinach', name: 'Spinach (cooked)', category: 'food', servingSize: '1 cup', servingGrams: 180, calories: 41, protein: 5.3, carbs: 6.8, fat: 0.5, fiber: 4.3, waterMl: 160 },
  { id: 'carrots', name: 'Carrots (raw)', category: 'food', servingSize: '1 cup', servingGrams: 128, calories: 52, protein: 1.2, carbs: 12, fat: 0.3, fiber: 3.6, waterMl: 108 },
  { id: 'tomato', name: 'Tomato', category: 'food', servingSize: '1 medium', servingGrams: 123, calories: 22, protein: 1.1, carbs: 4.8, fat: 0.2, fiber: 1.5, waterMl: 112 },
  { id: 'mixed-salad', name: 'Mixed Salad', category: 'food', servingSize: '2 cups', servingGrams: 110, calories: 20, protein: 1.5, carbs: 3.5, fat: 0.2, fiber: 2, waterMl: 100 },
  // Dairy & Alternatives
  { id: 'milk-whole', name: 'Whole Milk', category: 'drink', servingSize: '1 cup (240ml)', servingGrams: 244, calories: 149, protein: 8, carbs: 12, fat: 8, fiber: 0, waterMl: 220 },
  { id: 'milk-skim', name: 'Skim Milk', category: 'drink', servingSize: '1 cup (240ml)', servingGrams: 245, calories: 83, protein: 8.3, carbs: 12, fat: 0.2, fiber: 0, waterMl: 230 },
  { id: 'yogurt-plain', name: 'Plain Yogurt', category: 'food', servingSize: '1 cup', servingGrams: 245, calories: 149, protein: 8.5, carbs: 17, fat: 4, fiber: 0, waterMl: 210 },
  { id: 'greek-yogurt', name: 'Greek Yogurt (non-fat)', category: 'food', servingSize: '1 cup', servingGrams: 227, calories: 130, protein: 23, carbs: 7.5, fat: 0.7, fiber: 0, waterMl: 190 },
  { id: 'cheese-cheddar', name: 'Cheddar Cheese', category: 'food', servingSize: '30g', servingGrams: 30, calories: 113, protein: 7, carbs: 0.4, fat: 9.3, fiber: 0, waterMl: 10 },
  { id: 'butter', name: 'Butter', category: 'food', servingSize: '1 tbsp', servingGrams: 14, calories: 102, protein: 0.1, carbs: 0, fat: 11.5, fiber: 0, waterMl: 2 },
  // Drinks
  { id: 'water', name: 'Water', category: 'drink', servingSize: '1 glass (250ml)', servingGrams: 250, calories: 0, protein: 0, carbs: 0, fat: 0, fiber: 0, waterMl: 250 },
  { id: 'water-bottle', name: 'Water Bottle (500ml)', category: 'drink', servingSize: '500ml bottle', servingGrams: 500, calories: 0, protein: 0, carbs: 0, fat: 0, fiber: 0, waterMl: 500 },
  { id: 'coffee-black', name: 'Black Coffee', category: 'drink', servingSize: '1 cup (240ml)', servingGrams: 240, calories: 2, protein: 0.3, carbs: 0, fat: 0, fiber: 0, waterMl: 235 },
  { id: 'coffee-latte', name: 'Café Latte', category: 'drink', servingSize: '1 cup (350ml)', servingGrams: 350, calories: 135, protein: 7, carbs: 14, fat: 5.5, fiber: 0, waterMl: 290 },
  { id: 'tea', name: 'Tea (unsweetened)', category: 'drink', servingSize: '1 cup (240ml)', servingGrams: 240, calories: 2, protein: 0, carbs: 0.5, fat: 0, fiber: 0, waterMl: 235 },
  { id: 'orange-juice', name: 'Orange Juice', category: 'drink', servingSize: '1 cup (240ml)', servingGrams: 248, calories: 112, protein: 1.7, carbs: 26, fat: 0.5, fiber: 0.5, waterMl: 215 },
  { id: 'soda-cola', name: 'Cola/Soda', category: 'drink', servingSize: '1 can (355ml)', servingGrams: 355, calories: 140, protein: 0, carbs: 39, fat: 0, fiber: 0, waterMl: 315 },
  { id: 'soda-diet', name: 'Diet Soda', category: 'drink', servingSize: '1 can (355ml)', servingGrams: 355, calories: 0, protein: 0, carbs: 0, fat: 0, fiber: 0, waterMl: 340 },
  { id: 'beer', name: 'Beer (regular)', category: 'drink', servingSize: '1 can (355ml)', servingGrams: 355, calories: 153, protein: 1.6, carbs: 13, fat: 0, fiber: 0, waterMl: 300 },
  { id: 'protein-shake', name: 'Protein Shake', category: 'drink', servingSize: '1 scoop + water', servingGrams: 300, calories: 130, protein: 25, carbs: 3, fat: 2, fiber: 0, waterMl: 260 },
  { id: 'smoothie', name: 'Fruit Smoothie', category: 'drink', servingSize: '1 cup (350ml)', servingGrams: 350, calories: 185, protein: 3, carbs: 42, fat: 1, fiber: 3, waterMl: 280 },
  { id: 'agua-fresca', name: 'Agua Fresca (horchata)', category: 'drink', servingSize: '1 glass (350ml)', servingGrams: 350, calories: 140, protein: 2, carbs: 28, fat: 2.5, fiber: 0.5, waterMl: 290 },
  // Fats & Oils
  { id: 'olive-oil', name: 'Olive Oil', category: 'food', servingSize: '1 tbsp', servingGrams: 14, calories: 119, protein: 0, carbs: 0, fat: 14, fiber: 0, waterMl: 0 },
  // Snacks & Extras
  { id: 'almonds', name: 'Almonds', category: 'food', servingSize: '1 oz (28g)', servingGrams: 28, calories: 164, protein: 6, carbs: 6, fat: 14, fiber: 3.5, waterMl: 2 },
  { id: 'peanut-butter', name: 'Peanut Butter', category: 'food', servingSize: '2 tbsp', servingGrams: 32, calories: 188, protein: 8, carbs: 6, fat: 16, fiber: 2, waterMl: 2 },
  { id: 'protein-bar', name: 'Protein Bar', category: 'food', servingSize: '1 bar (60g)', servingGrams: 60, calories: 210, protein: 20, carbs: 22, fat: 7, fiber: 3, waterMl: 8 },
  { id: 'chips', name: 'Tortilla Chips', category: 'food', servingSize: '1 oz (28g)', servingGrams: 28, calories: 140, protein: 2, carbs: 18, fat: 7, fiber: 1.5, waterMl: 2 },
  // Mexican / commonly eaten in Zamora
  { id: 'tacos-pastor', name: 'Tacos al Pastor (3)', category: 'food', servingSize: '3 tacos', servingGrams: 250, calories: 470, protein: 28, carbs: 38, fat: 21, fiber: 4, waterMl: 100 },
  { id: 'burrito', name: 'Burrito (bean & cheese)', category: 'food', servingSize: '1 burrito', servingGrams: 250, calories: 410, protein: 16, carbs: 50, fat: 14, fiber: 8, waterMl: 100 },
  { id: 'enchiladas', name: 'Enchiladas (2)', category: 'food', servingSize: '2 enchiladas', servingGrams: 280, calories: 435, protein: 22, carbs: 38, fat: 20, fiber: 5, waterMl: 110 },
  { id: 'pozole', name: 'Pozole (1 bowl)', category: 'food', servingSize: '1 bowl', servingGrams: 400, calories: 325, protein: 20, carbs: 30, fat: 13, fiber: 4, waterMl: 250 },
  { id: 'quesadilla', name: 'Quesadilla', category: 'food', servingSize: '1 quesadilla', servingGrams: 120, calories: 290, protein: 11, carbs: 24, fat: 16, fiber: 2, waterMl: 40 },
  { id: 'sopes', name: 'Sopes (2)', category: 'food', servingSize: '2 sopes', servingGrams: 180, calories: 340, protein: 12, carbs: 36, fat: 16, fiber: 3, waterMl: 60 },
  { id: 'fruta-picada', name: 'Fruta Picada (fruta con chile)', category: 'food', servingSize: '1 cup', servingGrams: 200, calories: 90, protein: 1, carbs: 22, fat: 0.5, fiber: 3, waterMl: 160 },
  { id: 'elote', name: 'Elote (corn on the cob)', category: 'food', servingSize: '1 elote', servingGrams: 200, calories: 200, protein: 5, carbs: 30, fat: 7, fiber: 4, waterMl: 130 },
];

export function searchFood(query: string): FoodItem[] {
  if (!query.trim()) return FOOD_DB;
  const q = query.toLowerCase();
  return FOOD_DB.filter(f =>
    f.name.toLowerCase().includes(q) ||
    f.id.includes(q)
  );
}
