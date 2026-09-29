"""Minimal DDPE connection example."""

from ddpe.connect import DDPESession

# The DDPE Spark Connect server owns the application name.
spark = DDPESession.builder.getOrCreate()
spark.sql("SHOW DATABASES").show(truncate=False)
spark.stop()
