import type { components } from "../../shared/api-contracts";

export type CostCategory = components["schemas"]["CostItem"]["category"];

export const COST_CATEGORIES: CostCategory[] = ["往返交通", "住宿", "餐饮", "市内交通", "门票", "活动", "其他"];
