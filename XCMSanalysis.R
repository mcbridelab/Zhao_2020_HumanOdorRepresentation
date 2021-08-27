#XCMS portion of script lightly modified from Mohammed Khallaf, originally from Emmanuel Gaquerel
#Jessica Zung
#Princeton University
#jessica.zung (at) princeton.edu
#R3.6.1

#XCMS################################
library(xcms) #3.6.2
library(pracma) #2.2.9
library(multtest) #2.40.0
library(ggplot2) #3.3.2
library(gridExtra) #2.3

setwd("Zhao_human_odour_imaging/odour_profiles/xcms_analysis")
#should contain two folders, one for each treatment group, containing .mzxml GC-MS data files

#load in data and identify peaks
xset <- xcmsSet(method="centWave", ppm=30,peakwidth=c(3,50),snthresh=20)

#select retention time interval
RTrange <-c (360, 1500)#defining the retention time interval you want to look at
ix.rt <- which(xset@peaks[,"rt"] > RTrange[1] & xset@peaks[,"rt"] < RTrange[2]) #selecting all peaks with in the rt interval of interest
xset1 <- xset # copy xset
xset1@peaks <- xset@peaks[ix.rt,] #selects only the peaks that we want in the range and copy it into the new object
xset1 #check if the rt interval is correct

#align chromatograms
xset2 <- group(xset1,
               method = "density",
               minfrac = 0.1, #in what percent of samples
               minsamp = 1, #how many at least in a group
               bw = 10, #allowed difference in RT
               mzwid=0.1, #m/z accuracy
               sleep = 0.001)

xset3 <- retcor(xset2,
                method="obiwarp",
                profStep = 0.5,
                plottype = "none")

xset4 <- group(xset3,
               method = "density",
               mzwid = 0.1,
               sleep = 0.001, 
               minfrac = 0.1,
               minsamp = 1,
               bw = 5)

xset5 <- fillPeaks(xset4) #fill empty cells with zeros

an <- xsAnnotate(xset4) #creats PC groups
anF <- groupFWHM(an, perfwhm = 0.6)

reporttab <- diffreport(xset5, "HU", "AN", "results")
#this will create a file 'results.tsv' with XCMS output




#Group components################################

data <- read.table('results.tsv', sep='\t', header=T, row.names=1)

data2 <- data[order(data$rtmed),] #sort by RT

d <- data2[,14:34] #get just the component-abundance data across samples

res <- cor(t(d), method="pearson") #correlations between components


#Plot heatmap of correlations
par(mar=c(3,3,3,3))
col<- colorRampPalette(c("blue", "white", "red"))(50)

col <- colorRampPalette(c("blue", "white", "red"))(n = 299)
col_breaks = c(seq(-1,0, length=150),
               seq(0.01,1,length=150))

heatmap(x = res,
        col = col,
        symm = TRUE,
        cexCol = 1,
        cexRow=1,
        Rowv = NA,
        breaks=col_breaks)

#Now we want to group highly correlated ions that are also close together in RT

#Create columns in the dataframe
data2$ion_group <- 0
data2$ion_group_rt <- 0

#Correlation data are very noisy. So smooth out each row of the correlation matrix, and for
#each ion, try to see if there is a peak of highly correlated ions nearby (in RT).
#If so, assign the ion to the group defined by the ion at the centre of that peak.
for(i in 1:dim(data2)[1]){
  y <- res[i,] #one row of correlation matrix
  x <- c(1:length(y))
  
  fit <- loess(y ~ x, span=0.06)
  y.smooth <- predict(fit, data.frame(x = x)) #smoothed data
  
  peaks <- as.data.frame(findpeaks(y.smooth, minpeakheight=0.5)) #find peaks with max corr >=0.5
  if(length(peaks)==0) { #skip if no peaks found
    next
  }
  
  peaks$dist <- abs(data2$rtmed[i] - data2$rtmed[peaks[,2]]) #how far away is focal component from the correlation peak?
  if(min(peaks$dist) < 10){ #if close enough( <10s):
    data2$ion_group[i] <- peaks[peaks$dist==min(peaks$dist),2]
    data2$ion_group_rt[i] <- data2$rtmed[peaks[peaks$dist==min(peaks$dist),2]]
  }
}

#Groups at this point:
ion_groups <- data2[match(unique(data2$ion_group),data2$ion_group),c('ion_group','ion_group_rt')]

#In the previous step, the same "central" ion for a group wasn't always chosen.
#E.g., if ions 1,2,3,4 should be part of the same group, 1 might be in group "2",
#and 4 might be in group "3", but they really should all be together.
#Fix this by checking correlations among central group-defining ions.

cors <- data.frame(i=numeric(0), j=numeric(0), corr=numeric(0))

#loop over pairs of central ions
for(i in 2:dim(ion_groups)[1]){
  for(j in 2:dim(ion_groups)[1]){
    
    #if they are close together (<10s) in RT
    if(abs(ion_groups$ion_group_rt[i] - ion_groups$ion_group_rt[j]) < 10 && i<j){
      
      grp1 <- ion_groups$ion_group[i] #central ion for first group
      grp2 <- ion_groups$ion_group[j] #central ion for second group
      corr <- res[ion_groups$ion_group[i], ion_groups$ion_group[j]] #their correlation
      
      cors[dim(cors)[1]+1,] <- c(grp1, grp2, corr) #save to check
      
      if(corr > 0.5){ #if they are highly correlated, reassign all group 2 ions to group 1
        data2$ion_group[data2$ion_group==grp2] <- grp1
        data2$ion_group_rt[data2$ion_group==grp2] <- ion_groups$ion_group_rt[i]
      }
    }
  }
}


#Now collapse all ions in the same group
data3 <- data2[data2$ion_group!=0,] #ions in a group
data4 <- data2[data2$ion_group==0,] #ions not in a group
data4$name <- as.character(data4$name)

for(group in unique(data3$ion_group)){
  grp <- data3[data3$ion_group==group,]
  
  new_row <- data.frame(as.character(grp$name[1]),
                        NA,NA,NA,NA,NA,NA,
                        mean(grp$rtmed),
                        mean(grp$rtmin),
                        mean(grp$rtmax),
                        sum(grp$npeaks),
                        NA,NA,
                        t(colSums(grp[,14:34])), #sum ion abundances within a group
                        group,
                        mean(grp$ion_group_rt))
  
  colnames(new_row) <- colnames(data4)
  data4 <- rbind(data4, new_row)
}



#Find significantly enriched components################################

#convert to proportions
d <- data4[,14:34]
d2 <- apply(d,2,function(x){x/sum(x)})
data4[,14:34] <- d2

#create columns
data4$fold <- 0
data4$tstat <- 0
data4$pvalue <- 0

for(i in 1:dim(d2)[1]){
  animals <- d2[i,1:5]
  humans <- d2[i,6:21]
  
  W <- ks.test(animals,humans, alternative="two.sided") #Kolmogorov-Smirnov test
  fold <- log(mean(animals)/mean(humans),2) #fold change
  
  data4$fold[i] <- fold
  data4$tstat[i] <- W$statistic
  data4$pvalue[i] <- W$p.value
}

#Multiple test correction, using Benjamini-Hochberg
#http://www.metabolomics-forum.com/index.php?topic=164.0
crpval <- mt.rawp2adjp(data4[,"pvalue"], proc="BH")
idx <- sort(crpval$index, index.return=TRUE)
AdjPval <- crpval$adjp[idx$ix,2]
data4 <- cbind(data4[,1:4], AdjustedPval=AdjPval, data4[,5:ncol(data4)])


#save data
write.table(data4, 'results_normalized.tsv', sep='\t', row.names=F)

#Here, need to manually identify components in a new column, "cpd_name"
#and save the new file.

#read in file with components IDed
data5 <- read.table('results_norm_IDed.tsv', sep='\t', header=T)




#Volcano plots################################


#First, plot all compounds

colours = c(
  '#543DFF', #1-Hexanol
  '#2A14CC', #1-Octen-3-ol
  '#2A14CC', #1-Pentanol
  '#AA7BE2', #2-Heptanone
  '#CC14BA', #2,4-Dimethyl-1-heptene
  '#8C38AF', #Sulcatone
  '#4A113D', #Geranylacetone
  '#C1B2FF', #Acetoin
  '#14B6CC', #Benzaldehyde
  '#A7CC14', #Cedrol
  '#E60000', #Decanal
  '#14CC5E', #Dimethyl sulfone
  '#14CC5E', #Dimethyl trisulfide
  '#CC14BA', #Dodecane, 4,6-dimethyl-
  '#F9E219', #Heptanal
  '#14CC5E', #Isoamyl cyanide
  '#CC14BA', #Nonane
  '#14B6CC', #Phenol
  '#14CC5E') #Sulfide, allyl methyl

pdf('combinedVolcanoPlot.pdf',
    width=10, height=5,
    useDingbats=F)

ggplot(data5, aes(x=fold, y=-log(AdjustedPval, 10), col=as.factor(cpd_name))) +
  geom_point(size=2,aes(shape=cpd_name=="")) + 
  scale_color_manual(values=c('#E6E6E6', colours, '#E6E6E6')) + 
  scale_shape_manual(values=c(16,1)) +
  geom_hline(yintercept=1.3, linetype='dashed', colour='grey') +
  xlab('log2FoldChange') +
  ylab('-log10Pvalue') +
  theme_classic() +
  ggtitle("")

dev.off()




#Sometimes hard to see which compound is which.
#Plot individual volcano plots for each compound.
#Also make violin plots showing abundance of cpds across sample groups.


colours = c(
  '#A6A6A6', #Unknown
  '#14CC5E', #Sulfide, allyl methyl
  '#C1B2FF', #Acetoin
  '#2A14CC', #1-Pentanol
  '#CC14BA', #2,4-Dimethyl-1-heptene
  '#CC14BA', #Nonane
  '#14CC5E', #Isoamyl cyanide
  '#543DFF', #1-Hexanol
  '#AA7BE2', #2-Heptanone
  '#F9E219', #Heptanal
  '#14CC5E', #Dimethyl trisulfide
  '#2A14CC', #1-Octen-3-ol
  '#14B6CC', #Benzaldehyde
  '#8C38AF', #Sulcatone
  '#14CC5E', #Dimethyl sulfone
  '#14B6CC', #Phenol
  '#E60000', #Decanal
  '#CC14BA', #Dodecane, 4,6-dimethyl-
  '#4A113D', #Geranylacetone
  '#A7CC14') #Cedrol


#Need to reshape data for violin plots
data5_long <- reshape(data5,
                      direction = "long",
                      varying = list(names(data5[17:37])),
                      v.names = "Abund",
                      idvar = "name",
                      timevar = "cat",
                      times = c(rep("AN",5), rep("HU",16)))
data5_long$Abund[data5_long$Abund==0] <- 1e-7 #set zeroes to small positive value for log-scale plotting


i=1
#loop through IDed compounds
for(focal_cpd in unique(data5$cpd_name)[2:length(unique(data5$cpd_name))]){
  
  volcano <- ggplot(data5, aes(x=fold,y=-log(AdjustedPval, 10), col=cpd_name==focal_cpd)) +
    geom_point(size=2,aes(shape=cpd_name=="")) + 
    scale_color_manual(values=c('#E6E6E6', colours[i])) + 
    scale_shape_manual(values=c(16,1)) +
    geom_hline(yintercept=1.3, linetype='dashed', colour='grey') +
    xlab('log2FoldChange') +
    ylab('-log10Pvalue') +
    theme_classic() +
    ggtitle(focal_cpd) +
    theme(legend.position = "none")
  
  d <- subset(data5_long, cpd_name==focal_cpd)
  
  violins <- ggplot(d, aes(x=factor(name), y=Abund, fill=factor(cat))) +
    geom_violin(position=position_dodge(0.5), alpha = 0.4) +
    geom_dotplot(binaxis = 'y',
                 stackdir = 'center',
                 position = position_dodge(0.5),
                 binwidth = 0.1) +
    scale_fill_manual(values = c("#7C7C7C","red")) +
    scale_y_continuous(trans = "log10", limits = c(1e-7,1)) +
    ylab("Proportion of odour profile") +
    theme_classic() +
    theme(
      axis.title.x = element_blank(),
      axis.text.x = element_text(angle=90, hjust=1),
      axis.ticks.x = element_blank(),
      panel.grid.major = element_blank(),
      panel.grid.minor = element_blank(),
      strip.background = element_blank(),
      panel.border = element_blank())
  
  
  #grid.arrange(volcano, violins, nrow = 1)
  g1 <- arrangeGrob(volcano, violins, nrow = 1)
  ggsave(paste0('volcanoPlot_', focal_cpd, '.pdf'),
         g1, width = 10, height = 5, units = "in")
  
  
  i=i+1
}

