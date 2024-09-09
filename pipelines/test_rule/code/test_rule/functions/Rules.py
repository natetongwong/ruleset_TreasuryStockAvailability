from pyspark.sql import *
from pyspark.sql.functions import *
from pyspark.sql.types import *
from prophecy.utils import *

@execute_rule
def Rule1_ParseMaturityDate(maturity_date: Column=lambda: col("maturity_date")):
    return when(maturity_date.isNull(), substring(col("security_name"), - 4, 4))\
        .otherwise(maturity_date)\
        .alias("maturity_date")

@execute_rule
def Rule2_DefaultLocation(location: Column=lambda: col("location")):
    return when(location.isNull(), lit("AUS")).otherwise(location).alias("location")

@execute_rule
def Rule3_DefaultGL_Level_1(gl_level_1: Column=lambda: col("GL_Level_1")):
    return when(gl_level_1.isNull(), lit("bank001")).otherwise(gl_level_1).alias("GL_Level_1")

@execute_rule
def Rule4_DefaultGL_Level_2(gl_level_2: Column=lambda: col("GL_Level_2")):
    return when(gl_level_2.isNull(), lit("branch001")).otherwise(gl_level_2).alias("GL_Level_2")

@execute_rule
def Rule5_DefaultGL_Level_3(gl_level_3: Column=lambda: col("GL_Level_3")):
    return when(gl_level_3.isNull(), lit("Desk1")).otherwise(gl_level_3).alias("GL_Level_3")

@execute_rule
def Rule6_ParseCouponRate(security_name: Column=lambda: col("security_name")):
    return when(
          security_name.like("%\\%%"),
          concat(expr("substring(security_name, (locate('%', security_name) - 4), 4)"), lit("%"))
        )\
        .otherwise(lit(None))\
        .alias("coupon_rate")

@execute_rule
def Rule7_ExcludeFlag(trade_type: Column=lambda: col("TRADE_TYPE")):
    return when((trade_type == lit("loan")), lit("Y")).otherwise(lit("N")).alias("EXCLUDE")
