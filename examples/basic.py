"""Minimal DDPE connection example."""

from ddpe.connect import DDPESession

spark = (
    DDPESession.builder
    .remote("spark-connect.example:443")
    .getOrCreate()
)
spark.sql("SHOW DATABASES").show(truncate=False)
spark.stop()
