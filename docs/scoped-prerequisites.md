# 部分课程的学习前置范围

Topic 可通过 `prerequisite_scope_course_id` 指定学习解锁只检查某门课程内的前置。该课程必须实际包含此 Topic。

如果只开放课程的一部分，可同时配置 `prerequisite_scope_topic_ids`，列出这批已开放 Topic。列表必须非空、无重复，包含自身，且全部属于指定课程。解锁保留列表内部的源前置关系；递归检查也使用同一范围，避免通过内部祖先重新引入范围外的前置。

这些字段仅影响学习和复习资格，不修改原始图谱、课程归属、学习记录或测试材料可见性。没有这些字段的 Topic 沿用全局前置规则。范围内前置仍须完成当前版本学习、完成到期复习并解除暂停；管理员沿用既有预览权限。

修改范围或将只读源 Topic 升级为训练 Topic，必须先保存原始来源、验证完整题库，并核对没有需要迁移的旧学习记录。普通已开始的 Topic 不通过此流程覆盖。

隔离边界验收见 `tests/test_scoped_prerequisites.py`。

## Machine Learning 跨课程先修

Machine Learning I 和 II 中的非重叠 MA Topic，根据同一 Topic ID 的课程成员关系，将已在统计课程覆盖的 ML Topic 视为满足的先修。已核验的课程为 Linear Algebra、Probability & Statistics、Complex Analysis、Calculus I 和 Mathematics for Machine Learning 的两份课程图谱。

遇到这些已覆盖的节点，学习解锁、复习资格和生产选题都在该节点结束先修检查。其余先修继续执行当前的学习、复习和暂停规则。原始图谱及学习进度按各自的原始来源保存。工作流可通过 `DependencyPolicy.ma_covered_topics` 和 `prerequisite_parents` 使用同一覆盖与遍历口径。
