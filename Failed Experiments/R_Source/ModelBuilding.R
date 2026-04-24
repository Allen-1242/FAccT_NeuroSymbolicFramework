# ────────────────────────────────────────────────
# Counterfactual generation for California SNAP data
# ────────────────────────────────────────────────

library(data.table)
library(dplyr)
library(iml)
library(ranger)

library(counterfactuals)

#install.packages('iml')
#install.packages('ranger')
#library(ranger)

source("/home/dev/Masters_Thesis/Neuro_Symbolic/R_Source/Rules_Generator.R")



# ---- Load & clean data ----
data <- fread("/home/dev/Masters_Thesis/Neuro_Symbolic/qc_pub_fy2023_2.csv")

keep <- c(
  "YRMONTH", "STATENAME", "CERTHHSZ", "FSDEPDED", "FSMEDDED",
  "FSSLTEXP", "FSEARN", "FSUNEARN", "FSDIS", "FSELDER", "HOMELESS_DED"
)

data <- data[, ..keep]
data <- data[STATENAME == "California" & YRMONTH > 202212]
data[is.na(data)] <- 0
data$FSELDER <- as.factor(data$FSELDER)
data$FSDIS   <- as.factor(data$FSDIS)

# ---- Generate eligibility label ----
results <- snap_md_eligibility(data)
data$IS_APPROVED <- as.factor(ifelse(results$eligible, 1, 0))

# ---- Prepare modeling data ----
train_df <- data %>%
  select(CERTHHSZ, FSDEPDED, FSMEDDED, FSSLTEXP,
         FSEARN, FSUNEARN, FSDIS, FSELDER,
         HOMELESS_DED, IS_APPROVED)

# ---- Train lightweight random forest ----
set.seed(42)
train_df$IS_APPROVED <- as.factor(train_df$IS_APPROVED)

rf_model <- ranger(
  IS_APPROVED ~ .,
  data = train_df,
  probability = TRUE,        # classification inferred automatically
  importance = "impurity"
)

# ---- Custom predict wrapper for ranger ----
ranger_predict <- function(model, newdata) {
  preds <- predict(model, data = newdata, type = "response")$predictions
  as.data.frame(preds)
}

# ---- Wrap the model with iml Predictor ----
predictor <- Predictor$new(
  model = rf_model,
  data  = train_df %>% select(-IS_APPROVED),
  y     = train_df$IS_APPROVED,
  predict.function = ranger_predict,   # ✅ key fix
  type  = "prob"
)

# ---- Pick a factual instance ----
x_interest <- train_df %>% select(-IS_APPROVED)
cfact_idx  <- 1999
factual    <- x_interest[cfact_idx, ]

# ---- Generate counterfactual ----
MOC_classif <- MOCClassif$new(
  predictor,
  fixed_features = c("FSEARN", "FSUNEARN")
)

cfactuals <- MOC_classif$find_counterfactuals(
  factual,
  desired_class = "X1", 
  desired_prob  = c(0.5, 1)
)

# ---- Inspect ----
print(cfactuals)
cfactuals$data
