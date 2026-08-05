"""测试数据清理工具。

清理 description = TEST_ORG_DESCRIPTION 的测试组织及其下属成员、团队、供应商、用户。

策略：先创建 dsp_member 的备份表，删成员后用备份表关联清理团队/供应商/用户。
注意：需要先删除引用 dsp_user 的表（如 dsp_project），避免外键约束错误。
"""

from common.db_util import pg_db
from common.base_log import logger
from config.settings import TEST_ORG_DESCRIPTION


def cleanup_test_data():
    """
    清理 description = TEST_ORG_DESCRIPTION 的测试数据。

    清理顺序：
      项目 → 数据集 → 成员 → 团队 → 供应商 → 用户 → 组织
    """
    with pg_db.get_cursor() as cursor:
        logger.info("========== 开始清理测试数据 ==========")

        # 1) 创建 dsp_member 备份表（删成员后仍需通过它关联团队/供应商/用户）
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS dsp_member_backup AS "
            "SELECT * FROM dsp_member WHERE organization_id IN ("
            "  SELECT id FROM dsp_organization WHERE description = %s"
            ")",
            (TEST_ORG_DESCRIPTION,),
        )
        backup_count = cursor.rowcount
        logger.info(f"备份成员记录: {backup_count} 条")

        # 2) 删项目（先删项目，解除 dsp_project.created_by_id 对 dsp_user 的 FK 引用）
        try:
            cursor.execute(
                "DELETE FROM dsp_project WHERE organization_id IN ("
                "  SELECT id FROM dsp_organization WHERE description = %s"
                ")",
                (TEST_ORG_DESCRIPTION,),
            )
            logger.info(f"删项目: {cursor.rowcount} 条")
        except Exception as e:
            logger.warning(f"删项目失败（可能表不存在）: {e}")

        # 3) 删数据集（先删数据集，解除 dsp_dataset.created_by_id 对 dsp_user 的 FK 引用）
        cursor.execute(
            "DELETE FROM dsp_dataset WHERE organization_id IN ("
            "  SELECT id FROM dsp_organization WHERE description = %s"
            ")",
            (TEST_ORG_DESCRIPTION,),
        )
        logger.info(f"删数据集: {cursor.rowcount} 条")

        # 4) 删成员
        cursor.execute(
            "DELETE FROM dsp_member WHERE organization_id IN ("
            "  SELECT id FROM dsp_organization WHERE description = %s"
            ")",
            (TEST_ORG_DESCRIPTION,),
        )
        logger.info(f"删成员: {cursor.rowcount} 条")

        # 5) 删团队（通过备份表关联 team_id + 直接 organization_id）
        cursor.execute(
            "DELETE FROM dsp_team WHERE id IN ("
            "  SELECT DISTINCT team_id FROM dsp_member_backup "
            "  WHERE team_id IS NOT NULL AND organization_id IN ("
            "    SELECT id FROM dsp_organization WHERE description = %s"
            "  )"
            ")",
            (TEST_ORG_DESCRIPTION,),
        )
        logger.info(f"删团队(成员关联): {cursor.rowcount} 条")
        cursor.execute(
            "DELETE FROM dsp_team WHERE organization_id IN ("
            "  SELECT id FROM dsp_organization WHERE description = %s"
            ")",
            (TEST_ORG_DESCRIPTION,),
        )
        logger.info(f"删团队(组织关联): {cursor.rowcount} 条")

        # 6) 删供应商（通过备份表关联 supplier_id + 直接 organization_id）
        cursor.execute(
            "DELETE FROM dsp_supplier WHERE id IN ("
            "  SELECT DISTINCT supplier_id FROM dsp_member_backup "
            "  WHERE supplier_id IS NOT NULL AND organization_id IN ("
            "    SELECT id FROM dsp_organization WHERE description = %s"
            "  )"
            ")",
            (TEST_ORG_DESCRIPTION,),
        )
        logger.info(f"删供应商(成员关联): {cursor.rowcount} 条")
        cursor.execute(
            "DELETE FROM dsp_supplier WHERE organization_id IN ("
            "  SELECT id FROM dsp_organization WHERE description = %s"
            ")",
            (TEST_ORG_DESCRIPTION,),
        )
        logger.info(f"删供应商(组织关联): {cursor.rowcount} 条")

        # 7) 删用户（通过备份表关联 user_id）
        cursor.execute(
            "DELETE FROM dsp_user WHERE id IN ("
            "  SELECT DISTINCT user_id FROM dsp_member_backup "
            "  WHERE organization_id IN ("
            "    SELECT id FROM dsp_organization WHERE description = %s"
            "  )"
            ")",
            (TEST_ORG_DESCRIPTION,),
        )
        logger.info(f"删用户: {cursor.rowcount} 条")

        # 8) 删组织
        cursor.execute(
            "DELETE FROM dsp_organization WHERE description = %s",
            (TEST_ORG_DESCRIPTION,),
        )
        logger.info(f"删组织: {cursor.rowcount} 条")

        # 9) 删除备份表
        cursor.execute("DROP TABLE IF EXISTS dsp_member_backup")
        logger.info("备份表已删除")

    logger.info("==================== 测试数据清理完成 ====================")
