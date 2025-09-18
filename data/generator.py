import csv
import random
from datetime import datetime, timedelta

# Config
rows = 100
filename = "data/sample_data.csv"

start_time = datetime.now()

with open(filename, mode="w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["timestamp", "soil_moisture", "temperature", "humidity"])

    for i in range(rows):
        ts = start_time + timedelta(minutes=i)
        soil_moisture = random.randint(200, 800)
        temperature = random.uniform(20, 35)
        humidity = random.uniform(40, 90)

        writer.writerow([ts.strftime("%Y-%m-%d %H:%M:%S"), soil_moisture, round(temperature, 2), round(humidity, 2)])

print(f"✅ Sample data generated in {filename}")
