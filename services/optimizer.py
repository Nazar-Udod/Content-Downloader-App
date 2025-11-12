def solve_knapsack_problem(items_to_optimize: list, mb_limit_str: str) -> (list, str | None):
    """
    Виконує алгоритм рюкзака (Метод гілок та меж).
    Повертає (список_оптимізованих_елементів, повідомлення_про_помилку)
    """
    try:
        mb_limit = float(mb_limit_str)
        processed_items = []
        free_items_indices = set()  # Елементи з нульовим розміром

        for i, item in enumerate(items_to_optimize):
            size = item.get('size_mb', 0.0)
            value = item.get('weight', 0)

            if value <= 0 or size < 0: continue  # Ігноруємо безцінні або "негативні"
            if size == 0.0:
                free_items_indices.add(i)  # Додаємо "безкоштовні"
                continue
            if size > mb_limit: continue  # Занадто великі

            processed_items.append({
                'value': value, 'size': size,
                'density': value / size, 'original_index': i
            })

        # --- Сам Алгоритм ---
        processed_items.sort(key=lambda x: x['density'], reverse=True)
        n = len(processed_items)
        Vbest = 0.0  # Найкраща знайдена цінність
        best_selection_indices = set()  # Індекси найкращого набору

        def calculate_bound(node_index: int, current_value: float, current_size: float) -> float:
            """Розраховує верхню межу (bound) для вузла."""
            bound = current_value
            total_size = current_size
            for i in range(node_index, n):
                item = processed_items[i]
                if total_size + item['size'] <= mb_limit:
                    total_size += item['size']
                    bound += item['value']
                else:
                    # Дробова частина
                    remaining_capacity = mb_limit - total_size
                    bound += item['density'] * remaining_capacity
                    break
            return bound

        def solve_knapsack(node_index: int, current_value: float, current_size: float,
                           current_selection_indices: list):
            """Рекурсивна функція вирішення."""
            nonlocal Vbest, best_selection_indices

            if node_index == n:  # Дійшли до кінця гілки
                if current_value > Vbest:
                    Vbest = current_value
                    best_selection_indices = set(current_selection_indices)
                return

            # --- Відсікання (Pruning) ---
            bound = calculate_bound(node_index, current_value, current_size)
            if bound <= Vbest:
                return  # Ця гілка не дасть кращого результату

            item = processed_items[node_index]

            # 1. Гілка "Взяти елемент" (якщо він влазить)
            if current_size + item['size'] <= mb_limit:
                current_selection_indices.append(item['original_index'])
                solve_knapsack(
                    node_index + 1,
                    current_value + item['value'],
                    current_size + item['size'],
                    current_selection_indices
                )
                current_selection_indices.pop()  # Backtrack

            # 2. Гілка "Не брати елемент"
            solve_knapsack(
                node_index + 1,
                current_value,
                current_size,
                current_selection_indices
            )

        # Запуск рекурсії
        solve_knapsack(0, 0.0, 0.0, [])

        # --- Формування результату ---
        # Об'єднуємо обрані елементи та "безкоштовні"
        final_indices = best_selection_indices.union(free_items_indices)

        optimized_results = [items_to_optimize[i] for i in final_indices]

        return optimized_results, None

    except Exception as e:
        return [], f"Помилка під час оптимізації: {e}"