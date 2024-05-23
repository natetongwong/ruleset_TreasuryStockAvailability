from prophecy.cb.server.base.ComponentBuilderBase import *
from pyspark.sql import *
from pyspark.sql.functions import *
from dataclasses import dataclass, field, replace

from prophecy.cb.server.base.datatypes import SString
from prophecy.cb.ui.UISpecUtil import getColumnsToHighlight, computeTargetName, SchemaFields, getColumnsInSchema, \
    getColumnsToHighlight2
from prophecy.cb.ui.uispec import *
from prophecy.utils import get_alias
from prophecy.cb.util.StringUtils import isBlank
from prophecy.cb.util.CSVUtils import parse_escaped_csv, unparse_escaped_csv, CSVParseException
from prophecy.cb.server.base.WorkflowContext import *

@dataclass(frozen=True)
class ParamError:
    paramName: str
    hasError: bool

class Transformation(ABC):
    pass

class SchemaTransform(ComponentSpec):
    name: str = "AddRule"
    category: str = "Transform"
    gemDescription: str = "Adds, edits, renames, or drops columns."
    docUrl: str = "https://docs.prophecy.io/low-code-spark/gems/transform/schema-transform"

    def optimizeCode(self) -> bool:
        return True

    @dataclass(frozen=True)
    class AddReplaceColumn(Transformation):
        sourceColumn: SString = SString("")
        expression: SColumn = SColumn("")

    @dataclass(frozen=True)
    class RenameColumn(Transformation):
        sourceColumn: SString = SString("")
        targetColumn: SString = SString("")

    @dataclass(frozen=True)
    class DropColumn(Transformation):
        sourceColumn: SString = SString("")

    @dataclass(frozen=True)
    class MissingColumn(Transformation):
        sourceColumn: SString = SString("")
        defaultValue: SColumn = SColumn("")

    @dataclass(frozen=True)
    class AddRule(Transformation):
        expression: SColumn = SColumn("")
        param_errors: List[ParamError] = field(default_factory=list)

    @dataclass(frozen=True)
    class SchemaTransformProperties(ComponentProperties):
        columnsSelector: List[str] = field(default_factory=list)
        transformations: List[Transformation] = field(default_factory=list)
        importString: str = ""
        importLanguage: str = "sql"
        activeTab: str = "transformations"

    def onButtonClick(self, state: Component[SchemaTransformProperties]):
        _transformations = state.properties.transformations
        _transformations.append(self.AddRule())
        return state.bindProperties(replace(state.properties, transformations=_transformations))

    def dialog(self) -> Dialog:
        selectBox = (SelectBox("Operation")
                     .addOption("Add/Replace Column", "AddReplaceColumn")
                     .addOption("Drop Column", "DropColumn")
                     .addOption("Rename Column", "RenameColumn")
                     .addOption("Add If Missing", "MissingColumn")
                     .addOption("Add Rule", "AddRule")
                     .bindProperty("record.kind"))
        add_replace = Condition() \
            .ifEqual(PropExpr("record.kind"), StringExpr("AddReplaceColumn")) \
            .then(
                ColumnsLayout(("1rem"), alignY=("end"))
                    .addColumn(
                        ColumnsLayout(("1rem"))
                            .addColumn(selectBox, "0.3fr")
                            .addColumn(
                                ExpressionBox("New Column")
                                    .bindPlaceholder("New column's name")
                                    .bindProperty("record.AddReplaceColumn.sourceColumn")
                                    .bindLanguage("plaintext"),
                                "0.2fr"
                            )
                            .addColumn(
                                ExpressionBox("Expression")
                                    .bindLanguage("${record.AddReplaceColumn.expression.format}")
                                    .bindPlaceholders()
                                    .withSchemaSuggestions()
                                    .bindProperty("record.AddReplaceColumn.expression.expression"),
                                "0.5fr",
                                overflow="visible"
                            ),
                            "1fr",
                            overflow=("visible")
                    )
                    .addColumn(ListItemDelete("delete"), width="content")
            )
        drop_col = Condition() \
            .ifEqual(PropExpr("record.kind"), StringExpr("DropColumn")) \
            .then(
                ColumnsLayout(("1rem"), alignY=("end"))
                    .addColumn(
                        ColumnsLayout("1rem")
                            .addColumn(selectBox, "0.3fr")
                            .addColumn(
                                ExpressionBox("Column to drop")
                                    .bindPlaceholder("column_to_drop")
                                    .bindProperty("record.DropColumn.sourceColumn")
                                    .bindLanguage("plaintext"),
                                "0.7fr"
                            )
                    )
                    .addColumn(ListItemDelete("delete"), width="content")
            )
        missing_col = Condition() \
            .ifEqual((PropExpr("record.kind")), (StringExpr("MissingColumn"))) \
            .then(
                ColumnsLayout(("1rem"), alignY=("end"))
                    .addColumn(
                        ColumnsLayout(("1rem"))
                            .addColumn(selectBox, "0.3fr")
                            .addColumn(
                                SchemaColumnsDropdown("Source Column Name")
                                    .withSearchEnabled()
                                    .bindSchema("component.ports.inputs[0].schema")
                                    .bindProperty("record.MissingColumn.sourceColumn")
                                    .showErrorsFor("record.MissingColumn.sourceColumn"),
                                "0.2fr"
                            )
                            .addColumn(
                                ExpressionBox("Default Value (if missing)")
                                    .bindLanguage("${record.MissingColumn.defaultValue.format}")
                                    .bindPlaceholders()
                                    .withSchemaSuggestions()
                                    .bindProperty("record.MissingColumn.defaultValue.expression"),
                                "0.5fr",
                                overflow="visible"
                            ),
                        "1fr",
                        overflow=("visible")
                    )
                    .addColumn(ListItemDelete("delete"), width="content")
            )
        rename_col = Condition() \
            .ifEqual(PropExpr("record.kind"), StringExpr("RenameColumn")) \
            .then(
                ColumnsLayout(("1rem"), alignY=("end"))
                    .addColumn(
                        ColumnsLayout(("1rem"))
                            .addColumn(selectBox, "0.3fr")
                            .addColumn(
                                SchemaColumnsDropdown("Old Column Name")
                                    .withSearchEnabled()
                                    .bindSchema("component.ports.inputs[0].schema")
                                    .bindProperty("record.RenameColumn.sourceColumn")
                                    .showErrorsFor("record.RenameColumn.sourceColumn"),
                                "0.3fr"
                            )
                            .addColumn(
                                ExpressionBox("New Column Name")
                                    .bindPlaceholder("New column name")
                                    .bindProperty("record.RenameColumn.targetColumn")
                                    .bindLanguage("plaintext"),
                                "0.4fr"
                            )
                    )
                    .addColumn(ListItemDelete("delete"), width="content")
            )
        add_rule = Condition() \
            .ifEqual(PropExpr("record.kind"), StringExpr("AddRule")) \
            .then(
            ColumnsLayout(("1rem"), alignY=("end"))
            .addColumn(
                ColumnsLayout(("1rem"))
                .addColumn(selectBox, "0.3fr")
                .addColumn(
                    BusinessRuleBox("Expression")
                    .bindLanguage("${record.AddRule.expression.format}")
                    .bindPlaceholders()
                    .withSchemaSuggestions()
                    .bindParamErrors("${record.AddRule.param_errors}")
                    .bindProperty("record.AddRule.expression.expression"),
                    "0.7fr",
                    overflow="visible"
                ),
                "1fr",
                overflow=("visible")
            )
            .addColumn(ListItemDelete("delete"), width="content")
        )
        transformations = StackLayout(gap=("1rem"), height=("100bh")) \
            .addElement(TitleElement("")) \
            .addElement(
                    OrderedList("Transformations")
                        .bindProperty("transformations")
                        .setEmptyContainerText("Add Transformation")
                        .addElement(
                            add_replace
                        )
                        .addElement(
                            drop_col
                        )
                        .addElement(
                            missing_col
                        )
                        .addElement(
                            rename_col
                        )
                        .addElement(
                            add_rule
                        )
                ) \
            .addElement(SimpleButtonLayout("New Rule", self.onButtonClick))
        bulkEdit = StackLayout(height="100%") \
            .addElement(
                NativeText("Edit the Reformat expressions in the field below. Use the format of \"(addrep|rename|drop|missing),name,expr\".")
            ).addElement(
                NativeText("Use ``...`` to wrap multi-line expressions.")
            ).addElement(
                Editor(height="100%", language="${component.properties.importLanguage}") \
                    .bindProperty("importString")
            )
        tabs = Tabs() \
            .bindProperty("activeTab") \
            .addTabPane(
                TabPane("Rule Set", "transformations").addElement(transformations)
            )
        return Dialog("Schema Transform")\
                .addElement(
                ColumnsLayout(height=("100%"))
                    .addColumn(PortSchemaTabs(selectedFieldsProperty=("columnsSelector")).importSchema(), "2fr")
                    .addColumn(VerticalDivider(), width="content")
                    .addColumn(tabs, "5fr")
            )

    def tf_to_csv(self, state: Component[SchemaTransformProperties]) -> Component[SchemaTransformProperties]:
        tfs = []
        for tf in state.properties.transformations:
            linepart = []
            if isinstance(tf, self.RenameColumn):
                linepart = ["rename", tf.sourceColumn.rawValue, tf.targetColumn.rawValue]
            elif isinstance(tf, self.AddReplaceColumn):
                linepart = ["addrep", tf.sourceColumn.rawValue, tf.expression.rawExpression]
            elif isinstance(tf, self.DropColumn):
                linepart = ["drop", tf.sourceColumn.rawValue]
            elif isinstance(tf, self.MissingColumn):
                linepart = ["missing", tf.sourceColumn.rawValue, tf.defaultValue.rawExpression]
            elif isinstance(tf, self.AddRule):
                linepart = ["addrule", tf.expression.rawExpression]
            tfs.append(linepart)
        csv_string = unparse_escaped_csv(tfs)
        return state.bindProperties(replace(state.properties, importString=csv_string))

    def csv_to_tf(self, state: Component[SchemaTransformProperties]) -> Component[SchemaTransformProperties]:
        tfs = []
        ilang = state.properties.importLanguage
        for line in parse_escaped_csv(state.properties.importString, field_min=2, field_max=3):
            tf_type = line[0].lower().strip()
            if tf_type == "rename":
                (source, target) = line[1:]
                source = source.strip()
                target = target.strip()
                tfs.append(self.RenameColumn(
                    SString(value=source, rawValue=source, format=ilang),
                    SString(value=target, rawValue=target, format=ilang)
                ))
            elif tf_type == "addrep":
                (source, tgtExp) = line[1:]
                source = source.strip()
                tgtExpCol = col(tgtExp.strip())
                tfs.append(self.AddReplaceColumn(
                    SString(value=source, rawValue=source, format=ilang),
                    SColumn(rawExpression=tgtExp, expression=tgtExpCol, usedColumns=[tgtExp], format=ilang)
                ))
            elif tf_type == "drop":
                source = line[1].strip()
                tfs.append(self.DropColumn(
                    SString(rawValue=source, value=source, format=ilang)
                ))
            elif tf_type == "missing":
                (source, defaultVal) = line[1:]
                tfs.append(self.MissingColumn(
                    SString(rawValue=source, value=source, format=ilang),
                    SColumn(rawExpression=defaultVal, expression=col(defaultVal), usedColumns=[], format=ilang)
                ))
            elif tf_type == "addrule":
                rule_expr = line[1].strip()
                tfs.append(self.AddRule(SColumn(rawExpression=rule_expr, expression=col(rule_expr), usedColumns=[], format=ilang)))
        return state.bindProperties(replace(state.properties, transformations=tfs))

    def validate(self, context: WorkflowContext, component: Component[SchemaTransformProperties]) -> List[Diagnostic]:
        diagnostics = []
        transformed_columns = []
        dropped_columns = []
        if component.properties.activeTab == "transformations":
            transforms = component.properties.transformations
            for idx, tf in enumerate(transforms):
                if isinstance(tf, SchemaTransform.AddReplaceColumn):
                    if tf.sourceColumn.diagnosticMessages is not None and len(tf.sourceColumn.diagnosticMessages) > 0:
                        for message in tf.sourceColumn.diagnosticMessages:
                            diagnostics.append(Diagnostic(f"properties.transformations[{idx}].sourceColumn", message, SeverityLevelEnum.Error))

                    if tf.sourceColumn.value is not None:
                        if(len(tf.sourceColumn.value) == 0):
                            diagnostics.append(Diagnostic(
                                f"properties.transformations[{idx}].sourceColumn",
                                "Target can't be empty.",
                                SeverityLevelEnum.Error
                            ))
                        elif len(tf.expression.rawExpression.strip()) == 0:
                            diagnostics.append(Diagnostic(f"properties.transformations[{idx}].expression.expression",
                                                        "Expression can't be empty.",
                                                        SeverityLevelEnum.Error
                                                        ))
                        else:
                            transformed_columns.append(tf.sourceColumn.value)
                    else:
                        pass

                if isinstance(tf, self.RenameColumn):
                    if tf.sourceColumn.diagnosticMessages is not None and len(tf.sourceColumn.diagnosticMessages) > 0:
                        for message in tf.sourceColumn.diagnosticMessages:
                            diagnostics.append(Diagnostic(f"properties.transformations[{idx}].sourceColumn", message, SeverityLevelEnum.Error))
                    if tf.targetColumn.diagnosticMessages is not None and len(tf.targetColumn.diagnosticMessages) > 0:
                        for message in tf.targetColumn.diagnosticMessages:
                            diagnostics.append(Diagnostic(f"properties.transformations[{idx}].targetColumn", message, SeverityLevelEnum.Error))

                    if tf.sourceColumn.value is not None and tf.targetColumn.value is not None:
                        if (len(tf.sourceColumn.value.strip()) == 0 or len(tf.targetColumn.value.strip()) == 0):
                            diagnostics.append(Diagnostic(
                                f"properties.transformations[{idx}]",
                                "Source and target columns can't be empty in Rename",
                                SeverityLevelEnum.Error
                            ))
                        elif (tf.sourceColumn.value == tf.targetColumn.value):
                            diagnostics += Diagnostic(
                                f"properties.transformations[{idx}]",
                                "Source and target columns are the same in Rename",
                                SeverityLevelEnum.Warning
                            )
                        else:
                            transformed_columns.append(tf.targetColumn.value)
                    else:
                        pass
                if isinstance(tf, self.DropColumn):
                    if tf.sourceColumn.diagnosticMessages is not None and len(tf.sourceColumn.diagnosticMessages) > 0:
                        for message in tf.sourceColumn.diagnosticMessages:
                            diagnostics.append(Diagnostic(f"properties.transformations[{idx}].sourceColumn", message, SeverityLevelEnum.Error))
                    if tf.sourceColumn.value is not None and len(tf.sourceColumn.value.strip()) == 0:
                        diagnostics.append(Diagnostic(
                            f"properties.transformations[{idx}]",
                            "Drop column can't be empty.",
                            SeverityLevelEnum.Error
                        ))

                if isinstance(tf, self.MissingColumn):
                    if tf.defaultValue.diagnosticMessages is not None and len(tf.defaultValue.diagnosticMessages) > 0 :
                        for message in tf.defaultValue.diagnosticMessages:
                            diagnostics.append(Diagnostic(f"properties.transformations[{idx}].defaultValue", message, SeverityLevelEnum.Error))

                    if tf.sourceColumn.value is not None:
                        if len(tf.sourceColumn.value.strip()) == 0:
                            diagnostics.append(Diagnostic(
                                f"properties.transformations[{idx}]",
                                "Source column can't be empty.",
                                SeverityLevelEnum.Error
                            ))
                        else:
                            if "." in tf.sourceColumn.value:
                                diagnostics.append(Diagnostic(
                                    f"properties.transformations[{idx}]",
                                    "Source column doesn't support nested columns",
                                    SeverityLevelEnum.Error
                                ))
                            else:
                                transformed_columns.append(tf.sourceColumn.value)
                if isinstance(tf, self.AddRule):
                    if len(tf.expression.rawExpression.strip()) == 0:
                            diagnostics.append(Diagnostic(f"properties.transformations[{idx}].expression.expression",
                                                          "Rule Expression can't be empty.",
                                                          SeverityLevelEnum.Error
                                                          ))
                    elif tf.expression.diagnosticMessages is not None and len(tf.expression.diagnosticMessages) > 0:
                        for message in tf.expression.diagnosticMessages:
                            diagnostics.append(Diagnostic(f"properties.transformations[{idx}].expression.expression", message,
                                                          SeverityLevelEnum.Error))
                    else:
                        rules: List[BusinessRule] = context.functions_context.rules
                        rule_output_name = None
                        for rule in rules:
                            if rule.matches_expression(tf.expression.rawExpression):
                                rule_output_name = rule.outputs[0].name
                                input_schema = StructType([structField for structField in component.ports.inputs[0].schema.fields if structField.name not in dropped_columns])
                                param_errors = rule.validate_inputs(input_schema, transformed_columns)
                                for (param_name, param_diags) in param_errors.items():
                                    for diagnostic in param_diags:
                                        diagnostics.append(replace(diagnostic, path=f"properties.transformations[{idx}].expression.expression"))
                            else:
                                continue
                        if rule_output_name is not None:
                            transformed_columns.append(rule_output_name)




        elif component.properties.activeTab == "advanced":
            try:
                for (idx, line) in enumerate(parse_escaped_csv(component.properties.importString, field_min=2, field_max=3)):
                    tf_type = line[0].lower()
                    rest_count = len(line[1:])
                    msg = None
                    allowed_tfs = ["rename", "addrep", "drop", "missing", "addrule"]
                    if tf_type not in allowed_tfs:
                        msg = f"Unknown operation '{tf_type}'. Acceptable values are 'rename', 'addrep', 'drop', or 'missing'."
                    elif tf_type == "rename" and rest_count != 2:
                        msg = f"'Rename Column' operation takes 2 arguments (src, target), got {rest_count}"
                    elif tf_type == "addrep" and rest_count != 2:
                        msg = f"'Add/Replace Column' operation takes 2 arguments (src, target), got {rest_count}"
                    elif tf_type == "drop" and rest_count != 1:
                        msg = f"'Drop Column' operation takes 1 argument (src), got {rest_count}"
                    elif tf_type == "missing" and rest_count != 2:
                        msg = f"'Add If Missing' operation takes 2 arguments (src, default), got {rest_count}"
                    elif tf_type == "addrule" and rest_count != 1:
                        msg = f"'Add Rule' operation takes 1 argument (rule_expr: rule_name( ) or rule_name(col1, col2,.., colN)) but got {rest_count}"

                    if msg is not None:
                        diagnostics.append(Diagnostic(f"properties.importString", msg, SeverityLevelEnum.Error))
            except CSVParseException as e:
                diagnostics.append(Diagnostic(f"properties.importString", str(e), SeverityLevelEnum.Error))

        return diagnostics

    def onChange(self, context: WorkflowContext, oldState: Component[SchemaTransformProperties],
                 newState: Component[SchemaTransformProperties]) -> Component[SchemaTransformProperties]:
        oldProps = oldState.properties
        newProps = newState.properties

        if oldProps.activeTab == "advanced" and newProps.activeTab == "transformations":
            try:
                newState = self.csv_to_tf(newState)
                newProps = newState.properties
            except CSVParseException:
                pass
        elif oldProps.activeTab == "transformations" and newProps.activeTab == "advanced":
            newState = self.tf_to_csv(newState)
            newProps = newState.properties

        usedColumnNames = []
        transformed_columns = []
        dropped_columns = []
        transformations = []
        for transformation in newProps.transformations:
            updated_transformation = transformation
            if isinstance(transformation, self.AddReplaceColumn):
                usedColumnNames.append(transformation.expression)
                transformed_columns.append(transformation.sourceColumn.value)
            elif isinstance(transformation, self.RenameColumn) and transformation.sourceColumn.value is not None:
                usedColumnNames.append(SColumn.getSColumn(transformation.sourceColumn.value))
                transformed_columns.append(transformation.targetColumn.value)
            elif isinstance(transformation, self.DropColumn) and transformation.sourceColumn.value is not None:
                dropped_columns.append(transformation.sourceColumn.value)
                usedColumnNames.append(SColumn.getSColumn(transformation.sourceColumn.value))
            elif isinstance(transformation, self.MissingColumn):
                usedColumnNames.append(SColumn.getSColumn(transformation.sourceColumn.value))
                transformed_columns.append(transformation.sourceColumn.value)
            elif isinstance(transformation, self.AddRule):
                all_param_errors = []
                rule_output_name = None
                for rule in context.functions_context.rules:
                    if rule.matches_expression(transformation.expression.rawExpression):
                        rule_output_name = rule.outputs[0].name
                        input_schema = StructType([structField for structField in newState.ports.inputs[0].schema.fields if structField.name not in dropped_columns])
                        param_errors = rule.validate_inputs(input_schema, transformed_columns)
                        for (param_name, param_diags) in param_errors.items():
                            all_param_errors.append(ParamError(paramName=param_name, hasError=(len(param_diags) > 0)))
                    else:
                        continue
                updated_transformation = replace(updated_transformation, param_errors=all_param_errors)
                if rule_output_name is not None:
                    transformed_columns.append(rule_output_name)
            transformations.append(updated_transformation)


        #breakpoint()
        usedCols = getColumnsToHighlight2(usedColumnNames, newState)
        return newState.bindProperties(replace(newProps, columnsSelector=usedCols, transformations=transformations))

    class SchemaTransformCode(ComponentCode):
        def __init__(self, newProps):
            self.props: SchemaTransform.SchemaTransformProperties = newProps

        def apply(self, spark: SparkSession, in0: DataFrame) -> DataFrame:
            out = in0
            for transformation in self.props.transformations:
                if isinstance(transformation, SchemaTransform().AddReplaceColumn):
                    out = out.withColumn(transformation.sourceColumn.value, transformation.expression.column())
                elif isinstance(transformation, SchemaTransform().RenameColumn):
                    out = out.withColumnRenamed(transformation.sourceColumn.value, transformation.targetColumn.value)
                elif isinstance(transformation, SchemaTransform().DropColumn):
                    out = out.drop(transformation.sourceColumn.value)
                elif isinstance(transformation, SchemaTransform().MissingColumn):
                    if transformation.sourceColumn.value not in in0.columns:
                        out = out.withColumn(transformation.sourceColumn.value, transformation.defaultValue.column())
                elif isinstance(transformation, SchemaTransform().AddRule):
                    out = out.withColumn(get_alias(transformation.expression.column()), transformation.expression.column())
            return out