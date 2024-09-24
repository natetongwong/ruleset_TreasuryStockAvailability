from pyspark.sql import *
from pyspark.sql.functions import *
from pyspark.sql.types import *
from prophecy.utils import *
from test_rule.functions import *
from . import *
from .config import *

def Subgraph_1(spark: SparkSession, subgraph_config: SubgraphConfig, in0: DataFrame) -> DataFrame:
    Config.update(subgraph_config)
    df_add_coupon_rate_rule = add_coupon_rate_rule(spark, in0)
    subgraph_config.update(Config)

    return df_add_coupon_rate_rule
