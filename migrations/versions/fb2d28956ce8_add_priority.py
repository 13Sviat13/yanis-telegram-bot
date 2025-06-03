"""Add Priority

Revision ID: fb2d28956ce8
Revises: 9b07e6173669
Create Date: 2025-05-29 13:43:01.692496

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fb2d28956ce8'
down_revision: Union[str, None] = '9b07e6173669'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.alter_column('priority',
               existing_type=sa.VARCHAR(50), # Старий тип
               type_=sa.INTEGER(),          # Новий тип
               nullable=False,
               server_default=sa.text('2'),   # Новий default для нових рядків
               # Додаємо USING clause для конвертації існуючих значень
               # Припускаємо, що старі значення були 'high', 'medium', 'low', 'normal'
               # і ми хочемо їх змапити на 3, 2, 1, 2 відповідно.
               # Якщо у вас були інші значення, адаптуйте CASE.
               # Якщо всі старі значення були 'normal', то можна спростити.
               postgresql_using="CASE "
                                "WHEN priority = 'high' THEN 3 "
                                "WHEN priority = 'medium' THEN 2 "
                                "WHEN priority = 'low' THEN 1 "
                                "WHEN priority = 'normal' THEN 2 " # Мапимо 'normal' на 2 (Середній)
                                "ELSE 2 " # Або NULL, або якесь інше значення за замовчуванням для невідомих
                                "END::INTEGER"
               )
    # Можливо, вам не потрібно було nullable=False, якщо раніше було True,
    # тоді nullable=False додається окремим alter_column або при створенні нової колонки.
    # Якщо ж nullable=False було і для VARCHAR, тоді все ОК.

    # ### end Alembic commands ###


def downgrade() -> None:
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.alter_column('priority',
               existing_type=sa.INTEGER(),
               type_=sa.VARCHAR(50),
               nullable=False, # Або True, якщо так було до змін
               server_default=sa.text("'normal'"), # Повертаємо старий default
               # Для downgrade теж може знадобитися USING, щоб конвертувати числа назад у рядки
               postgresql_using="CASE "
                                "WHEN priority = 3 THEN 'high' "
                                "WHEN priority = 2 THEN 'medium' " # Або 'normal', залежно від логіки
                                "WHEN priority = 1 THEN 'low' "
                                "ELSE 'normal' "
                                "END::VARCHAR"
                )