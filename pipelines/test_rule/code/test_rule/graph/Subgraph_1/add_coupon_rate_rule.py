from pyspark.sql import *
from pyspark.sql.functions import *
from pyspark.sql.types import *
from prophecy.utils import *
from prophecy.libs import typed_lit
from .config import *
from test_rule.functions import *

def add_coupon_rate_rule(spark: SparkSession, in0: DataFrame) -> DataFrame:
    return in0.withColumn(get_alias(Rule6_ParseCouponRate()), Rule6_ParseCouponRate())
