"""
Generatore di dati realistici per test di qualità del sistema di scheduling
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random


class RealisticDataGenerator:
    """Generatore di scenari di test realistici"""

    def __init__(self, seed=42):
        """Inizializza il generatore con seed per riproducibilità"""
        random.seed(seed)
        np.random.seed(seed)

    def generate_production_scenario(self, num_tasks=100, num_resources=10):
        """
        Genera scenario di produzione realistica

        Args:
            num_tasks: Numero di task da generare
            num_resources: Numero di risorse disponibili

        Returns:
            tuple: (tasks_df, calendar_slots_df, leaves_df)
        """
        # Genera task con distribuzione realistica delle ore
        tasks_df = self._generate_realistic_tasks(num_tasks, num_resources)

        # Genera calendari per le risorse
        calendar_slots_df = self._generate_complex_calendars(tasks_df, num_resources)

        # Genera assenze distribuite strategicamente
        leaves_df = self._generate_strategic_leaves(tasks_df, density=0.15)

        return tasks_df, calendar_slots_df, leaves_df

    def generate_high_load_scenario(self, num_tasks=200, num_resources=10):
        """
        Genera scenario con carico elevato

        Args:
            num_tasks: Numero di task (alto)
            num_resources: Numero di risorse

        Returns:
            tuple: (tasks_df, calendar_slots_df, leaves_df)
        """
        # Task con ore più variabili e priorità più concentrate
        tasks_df = self._generate_high_priority_tasks(num_tasks, num_resources)

        # Calendari con disponibilità ridotta
        calendar_slots_df = self._generate_reduced_calendars(tasks_df, num_resources)

        # Assenze più concentrate
        leaves_df = self._generate_strategic_leaves(tasks_df, density=0.25)

        return tasks_df, calendar_slots_df, leaves_df

    def generate_stress_scenario(self, num_tasks=500, num_resources=10):
        """
        Genera scenario di stress test

        Args:
            num_tasks: Numero di task (molto alto)
            num_resources: Numero di risorse

        Returns:
            tuple: (tasks_df, calendar_slots_df, leaves_df)
        """
        # Task con distribuzione estrema
        tasks_df = self._generate_extreme_tasks(num_tasks, num_resources)

        # Calendari con vincoli complessi
        calendar_slots_df = self._generate_complex_calendars(tasks_df, num_resources)

        # Assenze sovrapposte
        leaves_df = self._generate_overlapping_leaves(tasks_df, density=0.30)

        return tasks_df, calendar_slots_df, leaves_df

    def _generate_realistic_tasks(self, num_tasks, num_resources):
        """Genera task con distribuzione realistica"""
        tasks = []

        for i in range(1, num_tasks + 1):
            # Distribuzione realistica delle ore (più task piccoli, alcuni grandi)
            if random.random() < 0.6:  # 60% task piccoli
                hours = np.random.gamma(2, 2)  # Media ~4 ore
            elif random.random() < 0.3:  # 30% task medi
                hours = np.random.gamma(4, 3)  # Media ~12 ore
            else:  # 10% task grandi
                hours = np.random.gamma(8, 4)  # Media ~32 ore

            hours = max(0.5, min(80, hours))  # Limita tra 0.5 e 80 ore

            # Distribuzione priorità realistica
            priority = self._generate_realistic_priority()

            # Assegna risorsa
            user_id = random.randint(1, num_resources)

            tasks.append({
                'id': i,
                'name': f'Task_{i:03d}',
                'user_id': user_id,
                'remaining_hours': round(hours, 1),
                'priority_score': priority
            })

        return pd.DataFrame(tasks)

    def _generate_high_priority_tasks(self, num_tasks, num_resources):
        """Genera task con più alta priorità concentrate"""
        tasks = []

        for i in range(1, num_tasks + 1):
            # Ore più variabili
            hours = np.random.exponential(8)  # Distribuzione esponenziale
            hours = max(0.5, min(80, hours))

            # Più task ad alta priorità
            if random.random() < 0.4:  # 40% alta priorità
                priority = np.random.uniform(80, 100)
            elif random.random() < 0.4:  # 40% media priorità
                priority = np.random.uniform(40, 70)
            else:  # 20% bassa priorità
                priority = np.random.uniform(10, 40)

            user_id = random.randint(1, num_resources)

            tasks.append({
                'id': i,
                'name': f'HighLoad_Task_{i:03d}',
                'user_id': user_id,
                'remaining_hours': round(hours, 1),
                'priority_score': round(priority, 1)
            })

        return pd.DataFrame(tasks)

    def _generate_extreme_tasks(self, num_tasks, num_resources):
        """Genera task per stress test"""
        tasks = []

        for i in range(1, num_tasks + 1):
            # Distribuzione estrema delle ore
            if random.random() < 0.7:  # 70% task molto piccoli
                hours = np.random.uniform(0.5, 2)
            elif random.random() < 0.2:  # 20% task medi
                hours = np.random.uniform(5, 20)
            else:  # 10% task molto grandi
                hours = np.random.uniform(40, 80)

            # Priorità con distribuzione normale
            priority = np.random.normal(50, 20)
            priority = max(10, min(100, priority))

            user_id = random.randint(1, num_resources)

            tasks.append({
                'id': i,
                'name': f'Stress_Task_{i:03d}',
                'user_id': user_id,
                'remaining_hours': round(hours, 1),
                'priority_score': round(priority, 1)
            })

        return pd.DataFrame(tasks)

    def _generate_realistic_priority(self):
        """Genera priorità con distribuzione realistica"""
        rand = random.random()
        if rand < 0.2:  # 20% alta priorità
            return round(np.random.uniform(80, 100), 1)
        elif rand < 0.7:  # 50% media priorità
            return round(np.random.uniform(40, 70), 1)
        else:  # 30% bassa priorità
            return round(np.random.uniform(10, 40), 1)

    def _generate_complex_calendars(self, tasks_df, num_resources):
        """Genera calendari complessi ma realistici"""
        calendar_slots = []

        for resource_id in range(1, num_resources + 1):
            # Trova tutti i task per questa risorsa
            resource_tasks = tasks_df[tasks_df['user_id'] == resource_id]['id'].tolist()

            if not resource_tasks:
                continue

            # Genera calendario per questa risorsa
            calendar_type = random.choice(['full_time', 'part_time', 'flexible'])

            if calendar_type == 'full_time':
                # 8 ore, 5 giorni
                days = [0, 1, 2, 3, 4]  # Lun-Ven
                hour_from, hour_to = 9, 17
            elif calendar_type == 'part_time':
                # 6 ore, 5 giorni o 8 ore, 3 giorni
                if random.random() < 0.5:
                    days = [0, 1, 2, 3, 4]
                    hour_from, hour_to = 9, 15
                else:
                    days = [0, 2, 4]
                    hour_from, hour_to = 9, 17
            else:  # flexible
                # Orari variabili
                days = random.sample([0, 1, 2, 3, 4, 5], k=random.randint(4, 6))
                start_hour = random.randint(7, 10)
                duration = random.randint(6, 10)
                hour_from, hour_to = start_hour, start_hour + duration

            # Crea slot per ogni task di questa risorsa
            for task_id in resource_tasks:
                for day in days:
                    calendar_slots.append({
                        'task_id': task_id,
                        'dayofweek': day,
                        'hour_from': hour_from,
                        'hour_to': hour_to
                    })

        return pd.DataFrame(calendar_slots)

    def _generate_reduced_calendars(self, tasks_df, num_resources):
        """Genera calendari con disponibilità ridotta"""
        calendar_slots = []

        for resource_id in range(1, num_resources + 1):
            resource_tasks = tasks_df[tasks_df['user_id'] == resource_id]['id'].tolist()

            if not resource_tasks:
                continue

            # Calendari più restrittivi
            if random.random() < 0.3:  # 30% part-time estremo
                days = random.sample([0, 1, 2, 3, 4], k=3)
                hour_from, hour_to = 10, 14  # Solo 4 ore
            elif random.random() < 0.4:  # 40% part-time normale
                days = [0, 1, 2, 3, 4]
                hour_from, hour_to = 9, 15  # 6 ore
            else:  # 30% full-time
                days = [0, 1, 2, 3, 4]
                hour_from, hour_to = 9, 17  # 8 ore

            for task_id in resource_tasks:
                for day in days:
                    calendar_slots.append({
                        'task_id': task_id,
                        'dayofweek': day,
                        'hour_from': hour_from,
                        'hour_to': hour_to
                    })

        return pd.DataFrame(calendar_slots)

    def _generate_strategic_leaves(self, tasks_df, density=0.15):
        """Genera assenze distribuite strategicamente"""
        leaves = []

        # Periodo di pianificazione (prossimi 60 giorni)
        start_date = datetime.now().date() + timedelta(days=1)
        end_date = start_date + timedelta(days=60)

        for _, task in tasks_df.iterrows():
            if random.random() < density:
                # Genera assenza per questo task
                leave_start = start_date + timedelta(days=random.randint(0, 45))
                leave_duration = random.choice([1, 2, 3, 5])  # 1-5 giorni
                leave_end = leave_start + timedelta(days=leave_duration - 1)

                leaves.append({
                    'task_id': task['id'],
                    'date_from': leave_start,
                    'date_to': leave_end
                })

        return pd.DataFrame(leaves)

    def _generate_overlapping_leaves(self, tasks_df, density=0.30):
        """Genera assenze sovrapposte per stress test"""
        leaves = []

        start_date = datetime.now().date() + timedelta(days=1)

        # Crea alcuni periodi di assenze concentrate
        busy_periods = [
            (start_date + timedelta(days=10), 5),  # Settimana 2
            (start_date + timedelta(days=25), 3),  # Settimana 4
            (start_date + timedelta(days=40), 7),  # Settimana 6
        ]

        for _, task in tasks_df.iterrows():
            if random.random() < density:
                # Scegli un periodo busy o casuale
                if random.random() < 0.6:  # 60% nei periodi busy
                    period_start, max_duration = random.choice(busy_periods)
                    duration = random.randint(1, max_duration)
                    leave_start = period_start + timedelta(days=random.randint(0, 2))
                else:  # 40% casuale
                    leave_start = start_date + timedelta(days=random.randint(0, 50))
                    duration = random.randint(1, 4)

                leave_end = leave_start + timedelta(days=duration - 1)

                leaves.append({
                    'task_id': task['id'],
                    'date_from': leave_start,
                    'date_to': leave_end
                })

        return pd.DataFrame(leaves)


# Funzioni di utilità per i test
def generate_scenario(scenario_type='production', **kwargs):
    """
    Genera scenario di test specifico

    Args:
        scenario_type: 'production', 'high_load', 'stress'
        **kwargs: Parametri aggiuntivi

    Returns:
        tuple: (tasks_df, calendar_slots_df, leaves_df)
    """
    generator = RealisticDataGenerator()

    if scenario_type == 'production':
        return generator.generate_production_scenario(**kwargs)
    elif scenario_type == 'high_load':
        return generator.generate_high_load_scenario(**kwargs)
    elif scenario_type == 'stress':
        return generator.generate_stress_scenario(**kwargs)
    else:
        raise ValueError(f"Scenario type '{scenario_type}' not supported")


def print_scenario_stats(tasks_df, calendar_slots_df, leaves_df):
    """Stampa statistiche dello scenario generato"""
    print(f"\n📊 Scenario Statistics:")
    print(f"Tasks: {len(tasks_df)}")
    print(f"Resources: {tasks_df['user_id'].nunique()}")
    print(f"Total Hours: {tasks_df['remaining_hours'].sum():.1f}")
    print(f"Avg Hours per Task: {tasks_df['remaining_hours'].mean():.1f}")
    print(f"Calendar Slots: {len(calendar_slots_df)}")
    print(f"Leaves: {len(leaves_df)}")

    # Distribuzione priorità
    high_priority = len(tasks_df[tasks_df['priority_score'] >= 80])
    med_priority = len(tasks_df[(tasks_df['priority_score'] >= 40) & (tasks_df['priority_score'] < 80)])
    low_priority = len(tasks_df[tasks_df['priority_score'] < 40])

    print(f"\nPriority Distribution:")
    print(f"High (80-100): {high_priority} ({high_priority/len(tasks_df)*100:.1f}%)")
    print(f"Medium (40-79): {med_priority} ({med_priority/len(tasks_df)*100:.1f}%)")
    print(f"Low (10-39): {low_priority} ({low_priority/len(tasks_df)*100:.1f}%)")


if __name__ == "__main__":
    # Test del generatore
    print("Testing Realistic Data Generator...")

    # Test scenario produzione
    tasks, calendar, leaves = generate_scenario('production', num_tasks=100, num_resources=10)
    print_scenario_stats(tasks, calendar, leaves)

    # Test scenario stress
    tasks, calendar, leaves = generate_scenario('stress', num_tasks=500, num_resources=10)
    print_scenario_stats(tasks, calendar, leaves)
