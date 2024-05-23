from pyspark.sql import *
from pyspark.sql.functions import *
from pyspark.sql.types import *
from prophecy.utils import *
from prophecy.libs import typed_lit
from test_rule.config.ConfigStore import *
from test_rule.functions import *

def create_security_dataframe(spark: SparkSession) -> DataFrame:
    data = [("USDFED 5.82% 0829", )]
    # Define the schema
    schema = StructType([
StructField("security_name", StringType(), True)])
    # Create the DataFrame
    out0 = spark.createDataFrame(data, schema)

    return out0
